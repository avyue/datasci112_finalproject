FROM python:3.13-slim

# HF Spaces requires user 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user map_builder.py app.py ./

COPY --chown=user \
    data/MyLA311/MyLA311_Service_Request_Homeless_Encampment_Combined_2025_20260524.csv \
    data/MyLA311/

COPY --chown=user \
    data/LAHSA/LA_County_Homeless_Encampment_Request_Forms_with_precinct.csv \
    data/LAHSA/

COPY --chown=user \
    data/LAPD/LAPD_NIBRS_Offenses_Dataset_2024_to_2025_20260526.csv \
    data/LAPD/lapd_precincts_combined.csv \
    data/LAPD/

COPY --chown=user \
    data/census_indicators/qct_by_prec.csv \
    data/census_indicators/

COPY --chown=user \
    data/shelters/2025_HIC_All_Projects.csv \
    data/shelters/

EXPOSE 7860

# --workers 1: all data held in memory; multiple workers would duplicate it
# --timeout 120: allow enough time for the 32 MB CSV to load on startup
CMD ["gunicorn", "app:server", "--bind", "0.0.0.0:7860", "--workers", "1", "--timeout", "120"]
