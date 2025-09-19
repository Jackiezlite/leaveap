    # PythonAnywhere Deployment Notes


    1. Upload `leave_app_final.zip` to your PythonAnywhere Files and extract to e.g. `/home/yourusername/leave_app_final`

    2. Create virtualenv and install deps:

```
python3 -m venv ~/envs/leave_app
source ~/envs/leave_app/bin/activate
pip install --upgrade pip
pip install flask openpyxl pillow
```

3. In the Web tab, set the Working Directory to `/home/yourusername/leave_app_final` and the WSGI file to point to `wsgi.py` in this folder. The provided `wsgi.py` contains `from app import app as application`.

4. Set the environment variable `FLASK_SECRET` to a secure value in the Web tab.

5. Reload the web app.

Default admin credentials created automatically: login_name=`admin`, password=`admin`. Change immediately.
