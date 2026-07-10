import os

def patch():
    dockerfile_path = 'opencve-docker/Dockerfile'
    if not os.path.exists(dockerfile_path):
        return

    with open(dockerfile_path, 'r') as f:
        content = f.read()

    target = 'RUN git clone --depth 1 -b v${OPENCVE_VERSION} "${OPENCVE_REPOSITORY}" . || git clone --depth 1 -b ${OPENCVE_VERSION} "${OPENCVE_REPOSITORY}" .'
    
    # We insert Flask-User disable settings before USER_APP_NAME in settings.py
    replacement = target + """
RUN sed -i '/USER_APP_NAME/i \\\\    USER_ENABLE_CONFIRM_EMAIL = False' opencve/settings.py
RUN sed -i '/USER_APP_NAME/i \\\\    USER_SEND_REGISTERED_EMAIL = False' opencve/settings.py
RUN sed -i '/USER_APP_NAME/i \\\\    USER_SEND_PASSWORD_CHANGED_EMAIL = False' opencve/settings.py
RUN sed -i '/USER_APP_NAME/i \\\\    USER_SEND_USERNAME_CHANGED_EMAIL = False' opencve/settings.py
"""

    if 'USER_ENABLE_CONFIRM_EMAIL' not in content:
        content = content.replace(target, replacement)
        with open(dockerfile_path, 'w') as f:
            f.write(content)
        print("-> Successfully patched Dockerfile with registration email disable commands.")
    else:
        print("-> Dockerfile is already patched.")

if __name__ == '__main__':
    patch()
