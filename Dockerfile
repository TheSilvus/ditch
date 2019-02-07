FROM alpine:latest

COPY ./requirements.txt /app/requirements.txt

RUN apk --no-cache add python3 youtube-dl ffmpeg opus && \
        apk --no-cache add --virtual install_deps build-base python3-dev libffi-dev git && \
        pip3 install -r /app/requirements.txt && \
        apk del install_deps

COPY . /app/

WORKDIR /app
CMD ["python3", "-u", "src/main.py"]
