from dotenv import load_dotenv

load_dotenv()

from app import create_app as _create_app


def create_app(test_config=None):
    return _create_app(test_config)


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
