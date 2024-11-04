FROM continuumio/miniconda3

EXPOSE 5000
COPY app app
COPY env.yml env.yml
RUN conda env create --file env.yml -n lectify-backend && conda init
SHELL ["conda", "run", "-n", "lectify-backend", "/bin/bash", "-c"]

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "lectify-backend", "python", "app/app.py"]