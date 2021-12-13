# An Algorand Tutorial

The tutorial is found in the `docs` directory and can be viewed on GitHub Pages at:
<https://gmcgoldr.github.io/algorand-tut/>.

You can run the tutorial code with these steps:

```bash
# install pre-requisits
./install.sh
# build a new private network (in dev mode)
sudo -u algorand aad-make-node private_dev -f
# start the node daemons
sudo -u algorand aad-run-node private_dev start
# run the transfer
sudo -u algorand ./demo-transfer.py /var/lib/algorand/nets/private_dev/Primary
# run the app
sudo -u algorand ./demo-app.py /var/lib/algorand/nets/private_dev/Primary
# test the app
sudo -u algorand pytest test_app_vouch.py
# stop the node daemons
sudo -u algorand aad-run-node private_dev stop
```

NOTE: the project is not audited and should not be used in a production environment.

