FROM public.ecr.aws/lambda/python:3.8

## Install system dependencies
RUN yum check-update
RUN yum -y install libsndfile

## Install ffmpeg
RUN mkdir -p /usr/local/bin/ffmpeg
WORKDIR /usr/local/bin/ffmpeg
ADD ffmpeg-4.2.1-amd64-static.tar.xz .
RUN mv ffmpeg-4.2.1-amd64-static/ffmpeg .
RUN ln -s /usr/local/bin/ffmpeg/ffmpeg /usr/bin/ffmpeg

## Install lambda function dependencies
COPY app/requirements.txt ${LAMBDA_TASK_ROOT}/app/requirements.txt
RUN pip install -r ${LAMBDA_TASK_ROOT}/app/requirements.txt

## Set environment variables for changing write directory of python packages ( as lambda can only write to /tmp )
ENV NUMBA_CACHE_DIR=/tmp
ENV MPLCONFIGDIR=/tmp

## Copy function code and tests
COPY app ${LAMBDA_TASK_ROOT}/app
COPY tests ${LAMBDA_TASK_ROOT}/tests

## For local testing
COPY events ${LAMBDA_TASK_ROOT}/events
COPY .env ${LAMBDA_TASK_ROOT}

CMD ["app.handler.lambda_handler"]