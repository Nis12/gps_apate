import requests
import configparser
import os
import gzip
import shutil
import subprocess

from enum import Enum
from getpass import getpass
from datetime import date, datetime, timedelta

#curl_easy_setopt(curl, CURLOPT_NETRC_FILE, "/path/to/alternate/_netrc") # alternative netrc file path


class OperationSystem(Enum):
        windows = "nt"
        unix = "posix"


def update_netrc_file(is_create, path):
    def wait_correct_input(correct_answers, answers_count_limit=3):
        answers_count = 0
        while answers_count < answers_count_limit:
            answer = input()
            if answer in correct_answers:
                return answer
            answers_count += 1
        return ""

    print(
        """Требуется создание и настройка файла netrc, настроить его здесь? 
        Если нет, потребуется настроить вручную. Вы получите ссылки на ресурсы [y/n]"""
    )

    answer = wait_correct_input(["y", "n"])
    if answer == "n":
        print(
            """
            Зарегистрируйтесь на сайте NASA https://urs.earthdata.nasa.gov/
            Прочтите вводную по настройке netrc от NASA https://cddis.nasa.gov/Data_and_Derived_Products/CreateNetrcFile.html
            Больше информации о настройке netrc https://www.labkey.org/Documentation/wiki-page.view?name=netrc
            После этого снова запустите программу и продолжите настройку

            Нажмите Enter для выхода
            """
        )
        input()
        quit()
    elif answer != "y":
        print("Превышен лимит попыток")
        quit()

    print("Больше информации о настройке netrc https://www.labkey.org/Documentation/wiki-page.view?name=netrc")
    print("Вы зарегестрированы на сайте NASA (https://urs.earthdata.nasa.gov/)? [y/n]")
    answer = wait_correct_input(["y", "n"])
    if answer == "n":
        print("""
              Зарегистрируйтесь на сайте NASA https://urs.earthdata.nasa.gov/
              После этого снова запустите программу и продолжите настройку

              Нажмите Enter для выхода
              """)
        input()
        quit()
    elif answer != "y":
        print("Превышен лимит попыток")
        quit()

    print("Ввидете логин от учетной записи:")
    login = input()
    print("Ввидете пароль от учетной записи (ввод скрыт):")
    password = getpass()

    mode = "w" if is_create else "a"
    start_content_line = "" if is_create else "\n"
    content = start_content_line + "machine urs.earthdata.nasa.gov login " + login + " password " + password
    with open(path, mode) as fp:
        fp.write(content)
        fp.close()

    print("Файл netrc создан. Путь к файлу " + path + "\nОткройте его в текстовом редакторе и убедитесь, что данные верны.")

def netrc_file_is_available():
    need_to_create = True
    if OperationSystem.windows.value == os.name:
        profile_path = os.environ["USERPROFILE"]
        for root, dirs, file in os.walk(profile_path):
            if "_netrc" in file:
                need_to_create = False
        update_netrc_file(need_to_create, profile_path + "\\" + "_netrc")
        return True
    elif OperationSystem.unix.value == os.name:
        home_path = os.path.expanduser("~")
        for root, dirs, files in os.walk(home_path):
            if ".netrc" in files:
                need_to_create = False
        update_netrc_file(need_to_create, home_path + "/" + ".netrc")
        return True
    return False

def create_url(target_date: datetime):
    MAIN_URL = "https://cddis.nasa.gov/archive/gnss/data/daily"
    BRDC = "brdc"
    first_year_date = date(target_date.year, 1, 1)
    delta = target_date.date() - first_year_date
    day_number = delta.days + 1
    
    formated_day_number = str(day_number) + "0" if day_number > 99 else "0" + str(day_number) + "0"
    formated_year_number = target_date.year - 2000
    
    # Имя файла выглядит как brdc0880.25n.gz, где brdc неизменно, 0880 - номер по счету текущего дня в году, то есть сегодня 29.03.2025 - 88 день с начала года.
    # 27.03.2025 будет 0860. Ноль в конце неизменен. 25n - год за вычетом тысячной части, n - тип эфемерид. gz - формат.
    url = MAIN_URL + "/" + str(target_date.year) + "/" + BRDC + "/" + BRDC + formated_day_number + "." + str(formated_year_number) + "n.gz"
    
    return url

def download_file(target_date = datetime.now() - timedelta(days=+1), index = 0):
    url = create_url(target_date)
    print("Сформирован URL: " + url)
    print("Запрос эфемерид")

    request = requests.get(url)
    if request.status_code == 200:
        filename = url.split('/')[-1]
        with open(filename, 'wb') as fd:
            for chunk in request.iter_content():
                fd.write(chunk)
        fd.close()
        print("Эфемериды скачены")
        print("Дата эфемерид: " + target_date.strftime("%d.%m.%Y"))
        return filename
    else:
        new_index = index + 1
        if index < 5: 
            print("На " + target_date.strftime("%d.%m.%Y") + " нет эфемерид на дату или произошла ошибка при скачивании, попытка загрузки предыдущей версии")
            return download_file(target_date - timedelta(days=+1), new_index)
        else:
            print("Не удалось скачать эфемериды")
            return ""   

config = configparser.ConfigParser()
PARAMS_FILE_PATH = "params.ini"
    
config.read(PARAMS_FILE_PATH)

is_first_start = config.get("parameters", "is_first_start") == "1"
update_is_needed = False
if is_first_start and not netrc_file_is_available():
    print("Операционная система не поддерживается или имеет специфическую конфигурацию")
    quit()
elif is_first_start:
    print("Перед следующим шагом вам потребуется установить Hackrf https://hackware.ru/?p=8249")
    print("Генерация gps-sdr-sim")
    subprocess.run(["gcc", "gpssim_generator/gpssim.c", "-lm", "-O3", "-o", "gps-sdr-sim"])
    config.set("parameters", "is_first_start", "0")
    update_is_needed = True
else:
    last_update_date_str = config.get("update", "last_date")
    last_update_datetime = datetime.strptime(last_update_date_str, '%Y-%m-%d %H:%M:%S.%f')
    delta = datetime.now() - last_update_datetime
    update_is_needed = delta.days > 0

ephemeris_filename = ""
if update_is_needed:
    ephemeris_filename = download_file()
    if ephemeris_filename != "":
        current_filename = config.get("update", "last_file_name")
        if os.path.exists(current_filename) and os.path.exists(current_filename[:-3]) and os.path.exists(ephemeris_filename):
            print("Удаление предыдущей версии")
            os.remove(current_filename)
            os.remove(current_filename[:-3])
            
        with gzip.open(ephemeris_filename, 'rb') as f_in:
            with open(ephemeris_filename[:-3], 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        config.set("update", "last_date", str(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')))
        config.set("update", "last_file_name", ephemeris_filename)
        
        with open(PARAMS_FILE_PATH, "w") as params:
            config.write(params)

        subprocess.run(["./gps-sdr-sim", "-e", ephemeris_filename[:-3], "-l", "50.450441,30.523550,100", "-b", "8"])
    else:
        if is_first_start:
            print("Требуется подключение к интернету для загрузки эфемерид. Проверьте подключение к интернету и содержимое файла netrc")
            quit()
        else:
            print("Загрузка эфемерид завершилась ошибкой. Запуск с текущими эфемеридами")
else:
    print("Обновление эфемерид не требуется")

print("Запуск hackrf_transfer")
subprocess.run(["hackrf_transfer", "-t", "gpssim.bin", "-f", "1575420000", "-s", "2600000", "-a", "1", "-x", "0"])

