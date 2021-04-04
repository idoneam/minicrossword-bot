FROM python:3.9-slim-buster

COPY requirements.txt /
RUN python3 -m pip install -r /requirements.txt

COPY . /bot
WORKDIR /bot

ENTRYPOINT ["python3" "Main.py"]
