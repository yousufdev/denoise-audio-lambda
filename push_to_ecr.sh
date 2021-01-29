#!/bin/bash

docker build -t denoise_audio_lambda .
docker tag denoise_audio_lambda:latest 209505902627.dkr.ecr.us-east-1.amazonaws.com/denoise-audio:latest
aws ecr get-login-password | docker login --username AWS --password-stdin 209505902627.dkr.ecr.us-east-1.amazonaws.com
docker push 209505902627.dkr.ecr.us-east-1.amazonaws.com/denoise-audio:latest