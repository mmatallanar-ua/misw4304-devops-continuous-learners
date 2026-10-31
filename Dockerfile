# La imagen base viene de ECR Public para evitar los límites de descarga de Docker Hub en CodeBuild.
FROM public.ecr.aws/docker/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY application.py .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "application:application"]
