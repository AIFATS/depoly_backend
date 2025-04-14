# Use an official Python image as a base (you can change it if needed)
FROM python:3.13

# Set the working directory
WORKDIR /app

# Install necessary packages and dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    ca-certificates \
    wget \
    bash \
    sudo \
    gnupg2 \
    lsb-release

# Copy your install_brave.sh script into the container
COPY install_brave.sh /tmp/install_brave.sh

# Make the script executable
RUN chmod +x /tmp/install_brave.sh

# Run the script to install Brave
RUN /tmp/install_brave.sh

# Clean up the script after installation
RUN rm /tmp/install_brave.sh

# Print the Brave version
RUN brave-browser --version

# Print the path where Brave is installed
RUN which brave-browser

# Copy the FastAPI application into the container
COPY . /app

# Expose port 8000 for FastAPI
EXPOSE 8000

# Install the necessary Python dependencies for your FastAPI app (if any)
RUN pip install --no-cache-dir -r requirements.txt

# Set the default command to run the FastAPI app using Uvicorn
CMD ["uvicorn", "setup:app", "--host", "0.0.0.0", "--port", "8000"]
