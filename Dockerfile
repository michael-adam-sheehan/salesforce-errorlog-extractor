FROM node:dubnium-alpine3.10
ARG TARGET_USERNAME
ARG SFDX_AUTH_URL

WORKDIR /app

RUN apk update

RUN apk add --no-cache \
      bash \
      vim \
      zip \
      nginx \
      python3 \ 
      openrc \
      tini \
      busybox-initscripts \
      jq

COPY . .

ENV PATH /app/node_modules/.bin:$PATH

RUN yarn install 
RUN yarn global add sfdx-cli 
RUN sfdx --version
RUN sfdx plugins --core

RUN echo ${SFDX_AUTH_URL} > sfdxurlfile
RUN sfdx force:auth:sfdxurl:store --sfdxurlfile=sfdxurlfile --setdefaultdevhubusername --setalias=DevHub
RUN rm sfdxurlfile

RUN python3 -m pip install pytest
RUN python3 setup.py install && pytest -sv

RUN mkdir -p /run/nginx
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/

EXPOSE 80

STOPSIGNAL SIGTERM

CMD ["nginx", "-g", "daemon off;"]
