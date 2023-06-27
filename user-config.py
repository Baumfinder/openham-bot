import openham_bot_config as conf

#mylang = "en"
family = "openham"
usernames["openham"]["*"] = "OpenHam Bot"
authenticate["openham"] = ('OpenHam Bot', open(conf.wiki_password_file, "r").readline())

family_files["openham"] = "https://openham.wiki/api.php"
