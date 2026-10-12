# Python projects

Small, production-shaped Python applications by [GonService](https://gonserviceit.com.br/software-sob-demanda).
Each folder is an independent project with its own README, tests and Dockerfile; CI runs every one
of them on each change.

| Project | What it shows | Stack |
| --- | --- | --- |
| [flask-report-automation](flask-report-automation) | Upload a sales spreadsheet, get an HTML report, an Excel summary and a JSON API | Flask, openpyxl, pytest |
| [django-helpdesk](django-helpdesk) | Support tickets with SLA by priority, admin workflow and a public + staff REST API | Django, DRF, PostgreSQL |
| [fastapi-appointments](fastapi-appointments) | Online booking for a clinic or salon: free-slot calculation, no double booking, token-protected admin API | FastAPI, SQLAlchemy, SQLite, Jinja2 |
| [cloud-cost-checkup](cloud-cost-checkup) | CLI that scans an AWS account for waste and writes an HTML/JSON report with estimated monthly savings | boto3, Jinja2, moto |
| [pdf-receipts](pdf-receipts) | Brazilian PDF receipts with amount in words and CPF/CNPJ validation, from a web form or a CSV batch | Flask, ReportLab |

## Em português

Projetos pequenos em Python, prontos para produção: cada pasta é um projeto independente, com
README, testes e Dockerfile. Precisa de algo parecido no seu negócio? Fale com a GonService:
[gonserviceit.com.br/software-sob-demanda](https://gonserviceit.com.br/software-sob-demanda) ·
[contato@gonserviceit.com.br](mailto:contato@gonserviceit.com.br)

## License

[MIT](LICENSE)
