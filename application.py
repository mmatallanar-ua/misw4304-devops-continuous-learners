from app import create_app

# Elastic Beanstalk busca por defecto un objeto llamado "application".
application = create_app()

if __name__ == "__main__":
    application.run()
