# An Algorand Tutorial

The tutorial is found in the `docs` directory and can be viewed on GitHub Pages at:
<https://gmcgoldr.github.io/algorand-tut/>.

You can run the tutorial code with these steps:

```bash
./install.sh
sudo -u algorand aad-run-node private_dev start
sudo -u algorand ./demo-transfer.py /var/lib/algorand/nets/private_dev/Primary
sudo -u algorand pytest tests_app_vouch.py
sudo -u algorand aad-run-node private_dev stop
```

NOTE: the project is not audited and should not be used in a production environment.

