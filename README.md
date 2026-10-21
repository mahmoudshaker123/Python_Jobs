# Python Jobs Portal

## Project Overview
The **Python Jobs Portal** aggregates Python, Django, backend, and Odoo opportunities from Wuzzuf, Bayt, and Mourjan. Sources are isolated so a temporary block or outage on one website never removes jobs collected from the others.

The project offers a seamless experience for both employers and job seekers. It collects job listings from multiple sources, updates them daily, and allows users to filter through various job categories. This makes it a one-stop destination for Python professionals seeking their next career opportunity.

## Features

### Key Features:
- **Automated Job Scraping:** The project uses Python’s BeautifulSoup library to scrape job listings from a variety of websites, ensuring that job seekers are always presented with the most up-to-date opportunities.

- **Multi-source Safety:** Wuzzuf, Bayt, and Mourjan update independently. Existing records are preserved whenever a source returns an error, an empty page, or a browser challenge.

- **Odoo Support:** Python and Odoo searches receive separate quotas, so Odoo results are not crowded out by larger Python result sets.

- **Background Task Management:** Celery, with Redis as a message broker, is used to handle background tasks such as scraping job data and updating the site daily. This ensures that all job listings are refreshed in real-time.

- **Comprehensive Job Search:** The portal provides an intuitive search and filter functionality for users to browse job listings based on their preferred job title, company, location, and other parameters.

- **Pagination and Data Organization:** Job listings are organized into multiple pages for better navigation. The portal ensures that the user experience remains fluid and intuitive even with a large number of job postings.

- **Responsive Design:** The front-end is designed to be responsive, ensuring users can access and interact with the portal from any device — whether it be desktop, tablet, or mobile.

- **Admin Panel for Data Management:** Django’s built-in admin interface is available for admins to manage job listings, users, and other key elements of the site.

- **Job Categories:** Users can filter jobs by category, making it easier for them to find the roles that best match their skill sets, such as Web Development, Data Science, DevOps, etc.

## Technology Stack

The Python Jobs Portal is built with a modern and scalable technology stack:

- **Python:** The backend logic is implemented using Python, which is well-suited for rapid development and robust performance.
- **Django:** The web framework used for the application, providing a strong MVC structure, easy-to-use ORM, and extensive features for handling user authentication, admin interface, and more.
- **PostgreSQL:** A powerful relational database management system that handles the storage and retrieval of job listings and user data.
- **Docker:** Containerization is used for easy deployment, allowing the application to be run seamlessly on any environment.
- **BeautifulSoup:** This library is used for web scraping job listings from external websites.
- **Celery & Redis:** Celery is used for handling asynchronous tasks such as scraping job data. Redis acts as the message broker for Celery tasks.
- **Bootstrap, HTML, CSS, JavaScript:** For building the responsive and interactive front-end interface.

## How It Works

### Web Scraping
The job listings are scraped from several job boards and company websites using BeautifulSoup. The scraper is automated, running daily through Celery tasks.

Run a complete refresh manually with:

```bash
python manage.py scrape_jobs
```

You can also select sources and cap each source independently:

```bash
python manage.py scrape_jobs --sources wuzzuf,mourjan --limit 40
```

Bayt may occasionally require an interactive browser challenge. In that case the command reports the block and preserves existing Bayt jobs; it does not try to bypass the website's protection.

### Automatic updates

`python manage.py update_jobs` refreshes every source, preserves sources that are temporarily unavailable, removes jobs older than 30 days, and records the result in the admin dashboard.

Production updates are triggered every hour by `.github/workflows/update-jobs.yml`. Add these repository secrets in GitHub:

- `SITE_URL`: the production URL, for example `https://python-careers.vercel.app`
- `CRON_SECRET`: the same random value configured in Vercel

The endpoint `/api/cron/update-jobs/` rejects requests without the matching Bearer token and uses a database lock to prevent overlapping runs.

Vercel Hobby only supports one native Cron invocation per day, so GitHub Actions is used for the hourly schedule. Vercel Pro users may move the same schedule into `vercel.json`.

## Vercel deployment

1. Create a managed PostgreSQL database (Neon, Supabase, or another provider) and copy its connection URL.
2. Import this Git repository into Vercel. Vercel detects `manage.py` and the Django WSGI application automatically.
3. Add the variables from `.env.example` to Vercel, especially `DATABASE_URL`, `SECRET_KEY`, and `CRON_SECRET`.

The Vercel build can inspect the Django project before those variables are available, using build-only fallback settings. The deployed application still requires both `SECRET_KEY` and `DATABASE_URL` at runtime and will fail closed if either is missing. After adding or changing an environment variable, redeploy so the new deployment receives it.

4. Run migrations against the production database from a trusted terminal:

```bash
vercel env pull .env.local
python manage.py migrate
python manage.py createsuperuser
```

5. Deploy production and configure the matching `SITE_URL` and `CRON_SECRET` GitHub repository secrets.

SQLite is retained only for local development. Production data must use the external PostgreSQL `DATABASE_URL` because Vercel Functions do not provide persistent local storage.

### Job Listings Storage
The job data is stored in a PostgreSQL database, which is then displayed on the front-end of the application.

### User Interaction
Users can visit the website to view job listings, apply filters to narrow down their search, and view detailed job descriptions.

### Admin Interface
Admins can manage and monitor the job listings from Django's powerful admin interface, including adding, updating, or deleting job posts.

## Setup Instructions

To set up the Python Jobs Portal on your local machine, follow these instructions:

1. **Clone the repository:**

```bash
git clone https://github.com/mahmoudshaker123/Python_Jobs.git
```

2. **Navigate to the project directory:**

```bash
cd Python_Jobs
```

3. **Build the Docker containers:**

```bash
docker-compose build
```

4. **Start the Docker containers in the background:**

```bash
docker-compose up -d
```

5. **Apply the migrations to set up the database:**

```bash
docker-compose exec web python manage.py migrate
```

6. **Create a superuser for accessing the Django admin interface:**

```bash
docker-compose exec web python manage.py createsuperuser
```

7. **Run the Django development server:**

```bash
docker-compose exec web python manage.py runserver
```

8. **Access the application by visiting:**

```
http://localhost:8000
```

## Contribution

We welcome contributions to improve the Python Jobs Portal project! If you'd like to contribute, follow these steps:

- Fork the repository.
- Create a new branch for your feature or bug fix.
- Implement your changes and test them locally.
- Submit a pull request with a clear description of the changes you made.

## License

This project is open source and available under the [MIT License](LICENSE).

## Conclusion

The **Python Jobs Portal** is a powerful tool for Python developers to stay up to date with the latest job opportunities. With its easy-to-use interface, automated job scraping, and background task management, it provides a seamless experience for users.

---

Feel free to customize this README further based on future updates or specific needs!
