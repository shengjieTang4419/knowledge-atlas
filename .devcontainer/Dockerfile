FROM mcr.microsoft.com/devcontainers/python:2-3.12-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_DEFAULT_INDEX=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/

RUN rm -f /etc/apt/sources.list.d/yarn.list && \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

# 时区
ENV TZ Asia/Shanghai
RUN ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
