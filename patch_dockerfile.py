import os

def patch():
    dockerfile_path = 'opencve-docker/Dockerfile'
    if not os.path.exists(dockerfile_path):
        return

    with open(dockerfile_path, 'r') as f:
        content = f.read()

    target = 'RUN git clone --depth 1 -b v${OPENCVE_VERSION} "${OPENCVE_REPOSITORY}" . || git clone --depth 1 -b ${OPENCVE_VERSION} "${OPENCVE_REPOSITORY}" .'
    
    replacement = target + """
RUN sed -i '/USER_APP_NAME/i \\\\    USER_ENABLE_CONFIRM_EMAIL = False' opencve/settings.py
RUN sed -i '/USER_APP_NAME/i \\\\    USER_SEND_REGISTERED_EMAIL = False' opencve/settings.py
RUN sed -i '/USER_APP_NAME/i \\\\    USER_SEND_PASSWORD_CHANGED_EMAIL = False' opencve/settings.py
RUN sed -i '/USER_APP_NAME/i \\\\    USER_SEND_USERNAME_CHANGED_EMAIL = False' opencve/settings.py
RUN sed -i 's|<meta name="csrf-token" content="{{ csrf_token() }} me">|<meta name="csrf-token" content="{{ csrf_token() }}"><meta name="subscriptions-url" content="{{ url_for(\\\\x27main.subscriptions\\\\x27) }}"/>|g' opencve/templates/base.html || true
RUN sed -i 's|<meta name="csrf-token" content="{{ csrf_token() }}">|<meta name="csrf-token" content="{{ csrf_token() }}"><meta name="subscriptions-url" content="{{ url_for(\\\\x27main.subscriptions\\\\x27) }}"/>|g' opencve/templates/base.html
RUN sed -i "s|url: '/subscriptions'|url: $('meta[name=subscriptions-url]').attr('content') || '/opencve/subscriptions'|g" opencve/static/js/custom.js
"""

    if 'subscriptions-url' not in content:
        # Re-apply full patch if missing subscriptions-url patch
        if 'USER_ENABLE_CONFIRM_EMAIL' in content:
            # Dockerfile was previously patched without subscriptions fix
            old_patch = target + """
RUN sed -i '/USER_APP_NAME/i \\\\    USER_ENABLE_CONFIRM_EMAIL = False' opencve/settings.py
RUN sed -i '/USER_APP_NAME/i \\\\    USER_SEND_REGISTERED_EMAIL = False' opencve/settings.py
RUN sed -i '/USER_APP_NAME/i \\\\    USER_SEND_PASSWORD_CHANGED_EMAIL = False' opencve/settings.py
RUN sed -i '/USER_APP_NAME/i \\\\    USER_SEND_USERNAME_CHANGED_EMAIL = False' opencve/settings.py
"""
            content = content.replace(old_patch, replacement)
        else:
            content = content.replace(target, replacement)
            
        with open(dockerfile_path, 'w') as f:
            f.write(content)
        print("-> Successfully patched Dockerfile with registration email disable and subscriptions URL fix commands.")
    else:
        print("-> Dockerfile is already patched.")

if __name__ == '__main__':
    patch()
