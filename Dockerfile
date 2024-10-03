FROM --platform=linux/amd64 docker.io/library/python:3.11-slim

# Ensures that Python output to stdout/stderr is not buffered: prevents missing information when terminating
ENV PYTHONUNBUFFERED=1

RUN groupadd -r user && useradd -m --no-log-init -r -g user user

RUN mkdir -p /opt/app /input /output  \
    && chown -R user:user /opt/app /input /output \
    && chmod -R 777 /output

USER user

WORKDIR /opt/app

ENV PATH="/home/user/.local/bin:${PATH}"

COPY --chown=user:user requirements.txt /opt/app/
COPY --chown=user:user ground_truth_nuclei_preliminary_3 /opt/app/ground_truth_nuclei_preliminary_3
COPY --chown=user:user ground_truth_nuclei_preliminary_10 /opt/app/ground_truth_nuclei_preliminary_10
COPY --chown=user:user ground_truth_nuclei_full_3 /opt/app/ground_truth_nuclei_full_3
COPY --chown=user:user ground_truth_nuclei_full_10 /opt/app/ground_truth_nuclei_full_10



COPY --chown=user:user ground_truth_tissue_preliminary /opt/app/ground_truth_tissue_preliminary
COPY --chown=user:user ground_truth_tissue_full /opt/app/ground_truth_tissue_full


# You can add any Python dependencies to requirements.txt
RUN python -m pip install \
    --user \
    --no-cache-dir \
    --no-color \
    --requirement /opt/app/requirements.txt

COPY --chown=user:user helpers.py /opt/app/
COPY --chown=user:user evaluate.py /opt/app/
COPY --chown=user:user eval_nuclei.py /opt/app/
COPY --chown=user:user evaluate_tissue.py /opt/app/


# Setting this will limit the number of workers used by the evaluate.py
#ENV GRAND_CHALLENGE_MAX_WORKERS=4

ENTRYPOINT ["python", "evaluate.py"]