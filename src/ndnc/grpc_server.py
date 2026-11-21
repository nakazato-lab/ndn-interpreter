"""Serve an NDN program through a generic execution-only gRPC interface."""
import asyncio
import logging
from pathlib import Path
import signal

import grpc
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .grpc import interpreter_pb2, interpreter_pb2_grpc
from .runtime import DeployedFunction
from .tracing import setup_tracing

LOG = logging.getLogger(__name__)


class InterpreterService(interpreter_pb2_grpc.InterpreterServicer):
    def __init__(self, source):
        self.source = Path(source).resolve()
        self.program = None

    async def Execute(self, request, context):
        parent = TraceContextTextMapPropagator().extract(
            dict(context.invocation_metadata()), context=Context())
        with trace.get_tracer(__name__).start_as_current_span(
                'ndnc.execute', context=parent, kind=trace.SpanKind.SERVER):
            # Check whether a regular file exists at this path.
            if self.program is None and not self.source.is_file():
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, 'Function source has not been deployed')
            try:
                if self.program is None:
                    self.program = DeployedFunction.load(self.source.read_text(encoding='utf-8'), self.source)
                result = await asyncio.wait_for(
                    self.program.execute(list(request.args)), timeout=context.time_remaining())
                if isinstance(result, bytes):
                    return interpreter_pb2.ExecutionResult(binary=result)
                return interpreter_pb2.ExecutionResult(text=result)
            except asyncio.TimeoutError:
                await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, 'Execution timed out')
            except Exception as exc:
                LOG.exception('Execution failed')
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))


async def serve(port, source):
    provider = setup_tracing('ndn-interpreter')
    server = grpc.aio.server(options=[('grpc.max_receive_message_length', -1),
                                     ('grpc.max_send_message_length', -1)])
    try:
        interpreter_pb2_grpc.add_InterpreterServicer_to_server(InterpreterService(source), server)
        if not server.add_insecure_port(f'0.0.0.0:{port}'):
            raise RuntimeError(f'Cannot bind gRPC port {port}')
        await server.start()
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        LOG.info('Interpreter listening on %s', port)
        try:
            await stop.wait()
        finally:
            await server.stop(grace=2)
    finally:
        if provider is not None:
            provider.shutdown()
