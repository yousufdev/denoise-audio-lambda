# Define global args
ARG FUNCTION_DIR="/home/audio_denoiser"
ARG RUNTIME_VERSION="3.9.6-slim"

# Stage 1 - bundle base image + runtime
# Grab a fresh copy of the image and install GCC if not installed ( In case of debian its already installed )
FROM python:${RUNTIME_VERSION} AS python-base

# Stage 2 - build function and dependencies
FROM python-base AS build-image
ENV LV2_PATH=/usr/local/lib/lv2:/usr/lib/lv2
# Install aws-lambda-cpp build dependencies ( In case of debian they're already installed )
RUN apt-get update && apt-get install -y \
    cmake \
    git \
    ninja-build \
    dh-autoreconf \
    pkg-config \
    lv2-dev
RUN pip install meson

RUN mkdir -p /github/lucianodato/speech-denoiser
WORKDIR /github/lucianodato/speech-denoiser
RUN git clone https://github.com/lucianodato/speech-denoiser.git .
RUN chmod +x install.sh && ./install.sh

# Include global args in this stage of the build
ARG FUNCTION_DIR
ARG RUNTIME_VERSION
# Create function directory
RUN mkdir -p ${FUNCTION_DIR}
# Copy handler function
COPY app/requirements.txt ${FUNCTION_DIR}/app/requirements.txt
# Optional – Install the function's dependencies
RUN pip install -r ${FUNCTION_DIR}/app/requirements.txt --target ${FUNCTION_DIR}
# Install Lambda Runtime Interface Client for Python
RUN pip install awslambdaric --target ${FUNCTION_DIR}

# Stage 3 - final runtime image
# Grab a fresh copy of the Python image
FROM python-base
# Include global arg in this stage of the build
ARG FUNCTION_DIR
# Set working directory to function root directory
WORKDIR ${FUNCTION_DIR}
# Copy in the built dependencies
COPY --from=build-image ${FUNCTION_DIR} ${FUNCTION_DIR}
COPY --from=build-image /usr/lib/lv2 /usr/lib/lv2
COPY --from=build-image /usr/local/lib/lv2 /usr/local/lib/lv2
# Install librosa system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg
# (Optional) Add Lambda Runtime Interface Emulator and use a script in the ENTRYPOINT for simpler local runs
# ADD https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie /usr/bin/aws-lambda-rie
# COPY entry.sh /
COPY app ${FUNCTION_DIR}/app
COPY tests ${FUNCTION_DIR}/tests
ENV NUMBA_CACHE_DIR=/tmp
ENV MPLCONFIGDIR=/tmp
ENV LD_LIBRARY_PATH=/usr/local/lib
ENV LV2_PATH=/usr/local/lib/lv2:/usr/lib/lv2
# RUN ln -s /usr/lib/x86_64-linux-gnu/libsndfile.so.1 /usr/local/lib/libsndfile.so.1
# enable below for local testing
COPY events ${FUNCTION_DIR}/events
COPY .env ${FUNCTION_DIR}
# RUN chmod 755 /usr/bin/aws-lambda-rie /entry.sh
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD [ "app.handler.lambda_handler" ]