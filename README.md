# An Algorand Tutorial

The tutorial is found in the `docs` directory and can be viewed on GitHub Pages at:
<https://gmcgoldr.github.io/algorand-tut/>.

You can run the tutorial code with these steps:

```bash
# install pre-requisits
./install.sh
# build a new private network (in dev mode)
aad-make-node nets/private_dev -f
# start the node daemons
aad-run-node nets/private_dev start
# run the transfer
./demo-transfer.py nets/private_dev/Primary
# run the app
./demo-app.py nets/private_dev/Primary
# test the app
pytest test_app_vouch.py
# stop the node daemons
aad-run-node nets/private_dev stop
```

NOTE: the project is not audited and should not be used in a production environment.
