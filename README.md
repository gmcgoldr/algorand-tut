# An Algorand Tutorial

The tutorial can be followed on GitHub Pages at:
<https://gmcgoldr.github.io/algorand-tut/>.

You can run the tutorial code with these steps:

```bash
./install.sh
sudo -u algorand aad-run-node private_dev start
sudo -u algorand ./demo-transfer.py /var/lib/algorand/nets/private_dev/Primary
sudo -u algorand aad-run-node private_dev stop
```
