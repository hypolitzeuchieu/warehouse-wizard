FROM python:3.11.5-bookworm AS builder


# set working directory
WORKDIR /app

# install dependencies
RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . .

EXPOSE  8000

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# run entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

#run the command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
