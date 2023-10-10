# Use an official Python 3.9 image
FROM python:3.8

# Set the working directory in the docker container
WORKDIR /app

# We copy just the pyproject.toml and poetry.lock files first to leverage Docker cache
COPY pyproject.toml poetry.lock ./

# Install necessary dependencies using poetry
RUN pip install poetry
RUN poetry config virtualenvs.create false \
&& poetry install --no-interaction --no-ansi --no-dev

# Copy the current directory contents into the container at /app
COPY . /app

# Add CMD command to run your application
CMD ["python", "main.py"]
