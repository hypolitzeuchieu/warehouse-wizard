# **Stock Management**

StockManagement is a stock management application that
allows managing products, stock movements, sales, and detailed reports.

## **Features**

- **Management of products, categories, and subcategories**
- **Recording of stock entries and exits**
- **Tracking of sales and returns**
- **Notifications for low or out-of-stock items**
- **Generation of inventory reports**
- **Local and remote synchronization with PostgreSQL**
- **Support for asynchronous tasks with Celery and Redis**

## **Prerequisites**

Make sure you have the following installed:

- **Docker and Docker Compose**
- **Python 3.11**
- **PostgreSQL**
- **Redis**

## **Installation**

### **1. Clone the repository**

Clone the repository and navigate to the project directory:

**Command Breakdown**

1. **Clone the repository**:
    ```bash
    git clone git@github.com:victmanagement/VictBackendManagement.git
    cd retailpulse
    ```

2. **Create the `.env` file** (configure environment variables).

3. **Build the Docker containers**:
    ```bash
    docker-compose up --build
    ```

4. **Apply database migrations**:
    ```bash
    docker-compose exec web python manage.py migrate
    ```

5. **Run the Django development server**:
    ```bash
    docker-compose exec web python manage.py runserver 0.0.0.0:8000
    ```

6. **Start the Celery worker**:
    ```bash
    docker-compose exec celery celery -A retailpulse worker --loglevel=info
    ```

7. **Stop all Docker services**:
    ```bash
    docker-compose down
    ```
