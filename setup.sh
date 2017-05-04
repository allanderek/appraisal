if [ ! -d "generated" ]; then
    mkdir generated
fi
# For some reason 3.6 might not work, just try 3.
virtualenv -p /usr/bin/python3.6 generated/venv
source develop.sh
pip install -r requirements.txt
npm install phantomjs
