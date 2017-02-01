import os
import downloader
import filenames
import utils
import data_parser

def init():
    ifNeedsUpdate = False
    if not os.path.exists("data"):
        ifNeedsUpdate = True
        os.makedirs("data")

    os.chdir("data")

    if not os.path.exists("prices"):
        os.makedirs("prices")

    if ifNeedsUpdate:
        update()

#даты при закачке смотреть отдельно для каждой платформы
def update():
    monetary_file = open(filenames.monetaryFile, "a+")
    monetary_file.seek(0)

    content = monetary_file.read()
    if content:
        last_date = content.splitlines()[-1].split(",")[0]
    else:
        last_date = ""
    monetary_file.write(downloader.get_net_mbase(last_date, dt.date.today().isoformat()))

    monetary_file.close()

    dates_file = open(filenames.datesFile, "a+")
    dates_file.seek(0)

    last_net_date = downloader.get_last_date()
    written_dates = dates_file.read().splitlines()

    if written_dates and utils.parse_isoformat_date(written_dates[-1]) == last_net_date:
        return

    platforms_file = open(filenames.platformsFile, "w")
    net_platforms = downloader.get_platforms()
    for code, name in net_platforms:
        if not os.path.exists(code):
            os.makedirs(code)
            os.makedirs("/".join([code, filenames.parsed]))
        platforms_file.write(code + " " + name + "\n")
    platforms_file.close()

    dates = downloader.get_dates(last_net_date)
    all_dates = downloader.get_net_dates()
    all_dates.append(last_net_date)
    all_dates.extend(dates)
    all_dates = sorted(list(set(all_dates)))

    for code, _ in net_platforms:
        index = data_parser.get_actives(code)
        for date in all_dates[len(written_dates):-1]:
            file = open(code + "/" + date.isoformat(), "w")

            if date == all_dates[-1]:
                data = downloader.get_current_actives(code)
            else:
                data = downloader.get_actives(date, code)

            data_parser.parse_date(code, date, data, index)

            file.write(data)
            file.close()

    for date in all_dates[len(written_dates):]:
        dates_file.write(date.isoformat() + "\n")
    dates_file.close()