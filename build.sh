#!/bin/bash

source .env.docker

docker build -t maxswjeon/certmanager:"$VERSION" .

docker tag maxswjeon/certmanager:"$VERSION" maxswjeon/certmanager:latest

docker push maxswjeon/certmanager:"$VERSION"
docker push maxswjeon/certmanager:latest
