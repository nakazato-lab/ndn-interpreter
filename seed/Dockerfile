FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml README.pypi.md LICENSE ./
COPY src/ ./src/
COPY seed/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt .

# seed/ をコピー
COPY seed/ ./seed/

# seed パッケージを import できるようにする
ENV PYTHONPATH=/app

CMD ["python3", "-m", "seed.main", "/seed"]
