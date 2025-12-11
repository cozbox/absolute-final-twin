ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install system dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    ffmpeg

# Copy requirements and install Python packages
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
COPY app /opt/app

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

# Set working directory
WORKDIR /opt

# Run the application
CMD [ "/run.sh" ]
