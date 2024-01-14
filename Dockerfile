FROM python:3.11-slim AS haiku-format-build

RUN apt-get update && apt-get install -y cmake g++ git ninja-build wget xz-utils

RUN git clone https://github.com/owenca/haiku-format && cd haiku-format && git checkout 66b8a40 && /bin/bash ./build.sh

FROM python:3.11-slim

COPY --from=haiku-format-build haiku-format/llvm-project/build/bin/clang-format /bin/haiku-format

RUN mkdir /app

COPY container/requirements.txt /app/requirements.txt

RUN pip install -r /app/requirements.txt

COPY formatchecker /app/formatchecker

WORKDIR /app
