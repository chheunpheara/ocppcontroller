FROM alpine:latest
FROM python:3.12.4

WORKDIR /ocppcontroller

COPY . /ocppcontroller

RUN apt update
RUN pip install -r requirements.txt

EXPOSE 3000
ENTRYPOINT [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000", "--reload" ]
