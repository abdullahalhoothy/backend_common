# Use the official Python image
FROM python:3.10

# Set the working directory in the container
WORKDIR /backend_common

# Copy the requirements file into the container
# Copy the rest of the application code into the container
COPY . .

# Install the dependencies
RUN pip install -r requirements.txt


# Command to run the FastAPI application with Uvicorn
CMD ["uvicorn", "run_apps:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]