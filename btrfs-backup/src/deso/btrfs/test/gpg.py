# gpg.py

#/***************************************************************************
# *   Copyright (C) 2015 Daniel Mueller (deso@posteo.net)                   *
# *                                                                         *
# *   This program is free software: you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License as published by  *
# *   the Free Software Foundation, either version 3 of the License, or     *
# *   (at your option) any later version.                                   *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU General Public License for more details.                          *
# *                                                                         *
# *   You should have received a copy of the GNU General Public License     *
# *   along with this program.  If not, see <http://www.gnu.org/licenses/>. *
# ***************************************************************************/

"""GnuPG public and private keys used for testing."""


PUBLIC_KEY = """
-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v2

mI0EVNk6UgEEANMHzMuT/3m/zaepfTkD6IA/cE0vs/h/lz7ve1E+9xFsC03+Y9pA
8ebhiJtLvdWANac9knZXD3ETj3h3K5zS9k6Q3hCqUqtVvLzsAMwO3HHDLO/eZQUo
/SGAiuHtop5Hv1pL5BOcSZBlSASLrG7OlZY5iK8FbsqS+b4SCn31MdbPABEBAAG0
F3Rlc3RlciA8dGVzdGVyQGRldm51bGw+iLgEEwECACIFAlTZOlICGwMHCwkIBwMC
AQYVCAIJCgsDFgIBAh4BAheAAAoJEFSa5ly68Xepk84EAJeE/tUaKq7ihVHwtc2B
JdH76ee9SgYvzpFbv1+J8hPwgQBTlMSJRC4kY64IDEGBsNYCoQYeVfcd4hRCQcyG
YlYB/rkFa8fYIajl1Ym1YSrOt697xFQUbICVxvprSTRuUCuE6hGMG5O96X8/ZvZh
MoaXJ9XkKUCy9EO95J9Rs9w2uI0EVNk6UgEEAO/DrEjAATFXhH97cmbhMnckfFXv
IIqmcBl1sIXGU+jZMav6xuYmZ/8BBuErzGU1EykfwPk+QXgrHPVcWUJc7nCe892l
tD4DXcQzWwP3WZ/uGKZwxNC/mHuMp3rHEX10z5P2x0dVzBQqtCdLCRUXuCgHrnE3
WUCHOnRrCqFCWnljABEBAAGInwQYAQIACQUCVNk6UgIbDAAKCRBUmuZcuvF3qUDj
A/9pnFqJNNUrQ5oqLEGghyFkMwwo8tpbEwShyPTaYbvLu46DooQT1JzklNrxsAoq
SgwKGNICpPSfxBxN2K2cZJycWBdoEa6ouNHk5AU3jtH3GQ6LWCoeo5FW2owTMw4H
iol+jhfThOG6CWxXTOoLIWgPmz8IoljBfqkwmJPYJG6WHg==
=+POW
-----END PGP PUBLIC KEY BLOCK-----
"""

PRIVATE_KEY ="""
-----BEGIN PGP PRIVATE KEY BLOCK-----
Version: GnuPG v2

lQHYBFTZOlIBBADTB8zLk/95v82nqX05A+iAP3BNL7P4f5c+73tRPvcRbAtN/mPa
QPHm4YibS73VgDWnPZJ2Vw9xE494dyuc0vZOkN4QqlKrVby87ADMDtxxwyzv3mUF
KP0hgIrh7aKeR79aS+QTnEmQZUgEi6xuzpWWOYivBW7Kkvm+Egp99THWzwARAQAB
AAP8DAlT2wCz/6O6/Scjp07bwgTcSOrBnxjX7ZUHOZkXynyZIHe0BkzR/1M50XG+
gCDx7noKkolgrhhphHt3l1hJCBOP9dwusYS0q1kc+AgVSnwPxKBYsKFS21+ipSTX
MmchdWv65G1xQSkuOb9bTLMh1rJEmx/rpCmvA52KdzZeH4ECANdwf8oLHykR6MpF
livkUHr+IEER4MCM6nEdVePwjG59jKlo8/Z5xnspJLvDy+oAXolRaKbPlbO5Qrxf
4ZLVlG8CAPrCzUVTnx4irNX22gsl+gP0I9gh5wsyHoI1eOWmEWpRyoXVFglpbfoN
JDCJ/Cs5LzBVChDoEdqDpVjPrbj406EB/iWZzrrqy/CpRaVdTqNnOEZ9qnZOAhUK
RSrE89jHc7CzH6591Q3SRJr5S3LxD+rw90RaqN4AIBbvS8KD1RBGSc+go7QXdGVz
dGVyIDx0ZXN0ZXJAZGV2bnVsbD6IuAQTAQIAIgUCVNk6UgIbAwcLCQgHAwIBBhUI
AgkKCwMWAgECHgECF4AACgkQVJrmXLrxd6mTzgQAl4T+1RoqruKFUfC1zYEl0fvp
571KBi/OkVu/X4nyE/CBAFOUxIlELiRjrggMQYGw1gKhBh5V9x3iFEJBzIZiVgH+
uQVrx9ghqOXVibVhKs63r3vEVBRsgJXG+mtJNG5QK4TqEYwbk73pfz9m9mEyhpcn
1eQpQLL0Q73kn1Gz3DadAdgEVNk6UgEEAO/DrEjAATFXhH97cmbhMnckfFXvIIqm
cBl1sIXGU+jZMav6xuYmZ/8BBuErzGU1EykfwPk+QXgrHPVcWUJc7nCe892ltD4D
XcQzWwP3WZ/uGKZwxNC/mHuMp3rHEX10z5P2x0dVzBQqtCdLCRUXuCgHrnE3WUCH
OnRrCqFCWnljABEBAAEAA/4lYdK4vQbylHyaC7s4gyAFJ3EjTNc8BtsvfQP6t4NZ
qJNwBvd/5rkMLzLNZLDHjtDf9o11ztkSTVaEgtN/31FlfHrwhSRu4ql5abzhg56N
BbW9YnveBLyYOdRV13GAfU0pf2ODyOFvOShpqb02C2jgwmAr9JuyYIMRNZMD7gdI
EQIA8WawDkW45klRrv/0JD7YGq23BkkAO43L+ywzx4AT65PC3Yug0w1yNjNEE6ky
0yi9ufKFl9I1nB4C+wD8/xkNjwIA/kOlJXaJWGX4eXmYmyH64QckuZKALZc2srBZ
fltZB9B3V4qkC6iIVdJXj/46vgxUUzj7Fj3CtUJhsBHSVepU7QIAs0MED+qQIYtG
vVYUJrwzYRo/OKoaycRVqq5kVFxZx899/tGSi0iMRZUC0g/EH8t8d9L12Ht7L9+H
YE1H74XJxZ4PiJ8EGAECAAkFAlTZOlICGwwACgkQVJrmXLrxd6lA4wP/aZxaiTTV
K0OaKixBoIchZDMMKPLaWxMEocj02mG7y7uOg6KEE9Sc5JTa8bAKKkoMChjSAqT0
n8QcTditnGScnFgXaBGuqLjR5OQFN47R9xkOi1gqHqORVtqMEzMOB4qJfo4X04Th
uglsV0zqCyFoD5s/CKJYwX6pMJiT2CRulh4=
=OGCT
-----END PGP PRIVATE KEY BLOCK-----
"""
