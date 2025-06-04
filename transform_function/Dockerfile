# 09.transform_function/Dockerfile
FROM mcr.microsoft.com/azure-functions/python:4-python3.9-slim

ENV AzureWebJobsScriptRoot=/home/site/wwwroot/transform_function \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    FUNCTIONS_WORKER_RUNTIME=python \
    PYTHON_ENABLE_WORKER_EXTENSIONS=1 \
    # این خط کلیدی است: به پایتون می‌گوید که در /home/site/wwwroot هم به دنبال ماژول‌ها بگردد
    PYTHONPATH=/home/site/wwwroot

# کپی کردن فایل نیازمندی‌ها از پوشه فانکشن مربوطه و نصب آنها
COPY transform_function/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# کپی کردن کل محتوای build context (که باید ریشه پروژه شما باشد) به /home/site/wwwroot
# این کار پوشه‌های 09.transform_function و 12.databricks و غیره را شامل می‌شود.
COPY . /home/site/wwwroot

# (اختیاری) ایجاد فایل‌های __init__.py خالی اگر لازم باشند و در سورس کنترل نیستند
# RUN mkdir -p /home/site/wwwroot/12.databricks && touch /home/site/wwwroot/12.databricks/__init__.py
# RUN mkdir -p /home/site/wwwroot/12.databricks/notebooks && touch /home/site/wwwroot/12.databricks/notebooks/__init__.py

# WORKDIR معمولاً لازم نیست به صراحت تنظیم شود اگر AzureWebJobsScriptRoot درست باشد
# WORKDIR /home/site/wwwroot