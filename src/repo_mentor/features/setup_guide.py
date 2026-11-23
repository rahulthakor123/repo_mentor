from repo_mentor.features.base import Feature, load_prompt
from repo_mentor.features.registry import register

KNOWN = {
    "fastapi": "A modern web framework for building APIs with Python.",
    "flask": "A lightweight web framework for Python.",
    "uvicorn": "A server that runs async web apps such as FastAPI.",
    "gunicorn": "A production server for running Python web apps.",
    "sqlalchemy": "A toolkit for working with SQL databases from Python.",
    "alembic": "A tool that manages database schema migrations.",
    "pydantic": "Validates data using Python type hints.",
    "pydantic-settings": "Loads app settings from environment variables and .env files.",
    "slowapi": "Adds rate limiting to FastAPI and Starlette apps.",
    "bcrypt": "Hashes passwords securely.",
    "pyjwt": "Creates and verifies JSON Web Tokens (JWT).",
    "python-jose": "Creates and verifies JSON Web Tokens (JWT).",
    "passlib": "Hashes and verifies passwords.",
    "python-multipart": "Lets web apps read form data and file uploads.",
    "pytest": "A testing framework for Python.",
    "httpx": "Makes HTTP requests from Python.",
    "requests": "Makes HTTP requests from Python.",
    "streamlit": "Builds web apps for data projects with Python.",
    "pandas": "Works with data in tables (dataframes).",
    "numpy": "Fast math on arrays of numbers.",
    "python-dotenv": "Loads settings from a .env file.",
    "psycopg": "Connects Python to PostgreSQL databases.",
    "psycopg2-binary": "Connects Python to PostgreSQL databases.",
    "werkzeug": "The toolkit Flask is built on for handling web requests and responses.",
    "jinja2": "A templating engine that fills HTML pages with data.",
    "markupsafe": "Escapes text so it is safe to put into HTML.",
    "itsdangerous": "Helps sign data safely, for example session cookies.",
    "click": "Builds command-line tools in Python.",
    "pytest-flask": "Fixtures and helpers for testing Flask apps with pytest.",
}


@register
class SetupGuideFeature(Feature):
    name = "setup_guide"
    description = "Exact steps to install and run the repo"

    def __init__(self, retriever, llm, facts_fn):
        super().__init__(retriever, llm)
        self.facts_fn = facts_fn

    @staticmethod
    def _steps(f, url: str, repo_dir: str) -> list[tuple[str, str]]:
        steps = []
        if f.language == "python":
            need = "Python 3" + (f" (the repo suggests `{f.python_hint}`)" if f.python_hint else "")
            steps.append(("Install the tools",
                          f"You need Git and {need}. Check them:\n```powershell\ngit --version\npython --version\n```"))
        else:
            steps.append(("Install the tools",
                          "You need Git and Node.js. Check them:\n```powershell\ngit --version\nnode --version\n```"))

        clone = f"git clone {url}\n" if url else "git clone <repo-url>\n"
        steps.append(("Get the code", f"```powershell\n{clone}cd {repo_dir}\n```"))

        if f.language == "python":
            steps.append(("Create a virtual environment",
                          "```powershell\npython -m venv .venv\n.venv\\Scripts\\Activate.ps1\n```\n"
                          "If PowerShell blocks the script, run "
                          "`Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` first. "
                          "On Mac/Linux use `source .venv/bin/activate`."))

        if f.install_cmd:
            steps.append(("Install the dependencies", f"```powershell\n{f.install_cmd}\n```"))

        if f.env_vars:
            names = ", ".join(f"`{v}`" for v in f.env_vars)
            if f.has_env_example:
                steps.append(("Set the environment variables",
                              "The code reads these variables. Copy the example file, then edit the values:\n"
                              f"```powershell\nCopy-Item .env.example .env\n```\nVariables used: {names}"))
            else:
                lines = "\n".join(f"{v}=your_value_here" for v in f.env_vars)
                steps.append(("Set the environment variables",
                              "The code reads these variables. Put them in a `.env` file or set them in your terminal:\n"
                              f"```\n{lines}\n```"))

        if f.run_cmd:
            web = any(k in f.run_cmd for k in ("streamlit", "uvicorn", "flask", "npm"))
            extra = "\nIf it is a web app, open the local URL printed in the terminal." if web else ""
            steps.append(("Run the project", f"```powershell\n{f.run_cmd}\n```{extra}"))
        return steps

    def _generate(self, repo_id, url, level):
        f = self.facts_fn(repo_id)
        repo_dir = url.rstrip("/").split("/")[-1] if url else repo_id.split("__", 1)[-1]

        if f.language == "unknown":
            yield "I couldn't work out how to run this repo.\n\n" + "\n".join(f"- {n}" for n in f.notes)
            return

        yield f"**Setup guide for `{repo_dir}`** ({f.language} project)\n\n"
        for i, (title, body) in enumerate(self._steps(f, url, repo_dir), 1):
            yield f"### {i}. {title}\n{body}\n\n"

        if f.packages:
            shown = f.packages[:15]
            yield "### What the libraries do\n"
            unknown = []
            for p in shown:
                desc = KNOWN.get(p.lower().replace("_", "-"))
                if desc:
                    yield f"- `{p}`: {desc}\n"
                else:
                    unknown.append(p)
            if unknown:
                user = "Packages:\n" + "\n".join(f"- {p}" for p in unknown)
                text = self.llm.generate(load_prompt("setup_guide", level), user)
                for line in text.splitlines():
                    line = line.strip()
                    if line.startswith(("-", "*")):
                        yield "- " + line.lstrip("-* ").strip() + "\n"
            if len(f.packages) > 15:
                yield f"\n- ...and {len(f.packages) - 15} more in the dependency file."
            yield "\n\n"

        if f.notes:
            yield "### Heads up\n" + "\n".join(f"- {n}" for n in f.notes)

    def run(self, repo_id, user_input="", level="beginner"):
        return {"answer": "".join(self._generate(repo_id, user_input, level)), "sources": []}

    def run_stream(self, repo_id, user_input="", level="beginner"):
        """user_input = the clean GitHub URL."""
        return self._generate(repo_id, user_input, level), []