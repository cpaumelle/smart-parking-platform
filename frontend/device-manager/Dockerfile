# syntax=docker/dockerfile:1

FROM nginx:alpine

ARG UI_VERSION=4.0.0
ARG UI_ENVIRONMENT=production

LABEL org.opencontainers.image.title="SenseMy UI"
LABEL org.opencontainers.image.version="${UI_VERSION}"
LABEL org.opencontainers.image.vendor="SenseMy"
LABEL org.opencontainers.image.description="Frontend for SenseMy IoT platform"
LABEL org.opencontainers.image.revision="${UI_ENVIRONMENT}"

# Health endpoint so compose can check container status
RUN printf '200 OK\n' > /usr/share/nginx/html/healthz

# Copy build output and nginx config
COPY dist/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
