r"""
        _____                                               
r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""
                 \/     \/           \/            \/       
"""

__title__ = "ofscraper"
__author__ = "datawhores"
__author_email__ = "datawhores@riseup.net"
__description__ = (
    "A command-line program to quickly download,like or unlike posts, and more"
)
__url__ = "https://github.com/datawhores/OF-Scraper"
__license__ = "GNU General Public License v3 or later (GPLv3+)"
__copyright__ = "Copyright 2023"

try:
    from dunamai import Version

    __hardcoded__ = None
    __version__ = __hardcoded__ or Version.from_git(
        pattern="(?P<base>\d+\.\d+\.((\d+\.\w+)|\w+))"
    ).serialize(format="{base}+{branch}.{commit}", metadata=False)
except:
    import pkg_resources

    __version__ = pkg_resources.get_distribution("ofscraper").version
