# SPDX-License-Identifier: AGPL-3.0-or-later
# Lo justo para calcular la previsión y publicarla: Python con numpy y Pillow
# (el radar), git y ssh (para publicar la web y subir los datos a IONOS con
# las claves de despliegue), Chromium sin pantalla y la letra Roboto (la
# gráfica del resumen como imagen, ADR 0098), y Claude Code, que usan el
# revisor de coherencia (ADR 0101), el reparador (ADR 0113) y otros
# automatismos del NAS desde este contenedor. Para el reparador, también lo
# que necesita para repetir las comprobaciones de GitHub: Ruff y Node (ESLint
# se instala en su copia del repositorio).
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Europe/Madrid \
    LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git openssh-client tzdata tini \
      python3 python3-numpy python3-pil \
      chromium fonts-roboto-unhinted nodejs npm \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -u 1000 -m -s /bin/bash jjdeharo

# Claude Code, con la versión fija: dentro del contenedor no se actualiza solo.
# Para subirla, se cambia este valor y se reconstruye.
ARG CLAUDE_CODE_VERSION=2.1.289
RUN mkdir -p /opt/claude \
 && curl -fsSL https://claude.ai/install.sh | HOME=/opt/claude bash -s "${CLAUDE_CODE_VERSION:-2.1.289}" \
 && ln -s /opt/claude/.local/bin/claude /usr/local/bin/claude \
 && chown -R 1000:1000 /opt/claude

# Ruff, la misma versión que la acción de GitHub (.github/workflows/previsio.yml).
ARG RUFF_VERSION=0.17.1
RUN curl -fsSL "https://github.com/astral-sh/ruff/releases/download/${RUFF_VERSION}/ruff-x86_64-unknown-linux-gnu.tar.gz" \
      | tar xz -C /usr/local/bin --strip-components=1 ruff-x86_64-unknown-linux-gnu/ruff

# Toda conexión ssh (git con GitHub, los datos a IONOS) da por muerta la que
# no responde en un minuto (ADR 0129): un corte de la red de casa a media
# conexión la dejaba colgada hasta que el sistema la cerraba, 2 h 11 min
# después, y el reloj no publicaba (19-11-2026, de 02:34 a 04:53).
RUN printf 'Host *\n  ServerAliveInterval 15\n  ServerAliveCountMax 4\n' \
      > /etc/ssh/ssh_config.d/conexio-viva.conf

COPY reloj.sh /usr/local/bin/reloj.sh
RUN chmod +x /usr/local/bin/reloj.sh

USER 1000
WORKDIR /proyecto
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/local/bin/reloj.sh"]
