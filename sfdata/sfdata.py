from functools import reduce #, partial
import numpy as np
import pandas as pd
import xarray as xr
from tqdm import tqdm

from .utils import typename, percentage_missing, strlen, maxstrlen, decide_color, print_line, dip
from .cprint import cprint


#unique_intersect1d = partial(np.intersect1d, assume_unique=True)
#TODO: how to handle non-unique pids?


class SFData(dict):

    names = property(dict.keys)
    channels = property(dict.values)

    @property
    def pids(self):
        return reduce(np.intersect1d, self._iter_pids())

    @property
    def all_pids(self):
        return reduce(np.union1d, self._iter_pids())

    def _iter_pids(self):
        return (c.pids for c in self.values())

    def to_dataframe(self, show_progress=False):
        all_pids = self.all_pids
        df = pd.DataFrame(index=all_pids, columns=self.names, dtype=object) # object dtype makes sure NaN can be used as missing marker also for int/bool
        channels = self.values()
        if show_progress:
            channels = tqdm(channels)
        for chan in channels:
            which = np.isin(all_pids, chan.pids)
            df.loc[which, chan.name] = chan.data.tolist() # TODO: workaround for pandas not dealing with ndim. columns
        return df

    def to_xarray(self, show_progress=False):
        ds = xr.Dataset()
        channels = self.values()
        if show_progress:
            channels = tqdm(channels)
        for chan in channels:
            data = chan.data
            coords = {"pids": chan.pids}
            dims = ["pids"] + [f"dim{i}" for i in range(1, data.ndim)]
            da = xr.DataArray(data, coords=coords, dims=dims)
            ds[chan.name] = da
        return ds

    def drop_missing(self, show_progress=False):
        shared_pids = self.pids
        channels = self.values()
        if show_progress:
            channels = tqdm(channels)
        for chan in channels:
            chan.reset_valid()
            _inters, ind_chan, _ind_shared = np.intersect1d(chan.pids, shared_pids, return_indices=True)
            chan.valid = ind_chan


    def print_stats(self, show_complete=False):
        print_line()
        shared_pids = self.pids
        all_pids = self.all_pids

        n_shared_pids = len(shared_pids)
        n_all_pids = len(all_pids)
        max_perc = percentage_missing(n_shared_pids, n_all_pids)

        len_pids = strlen(n_all_pids)
        len_perc = strlen(max_perc)
        len_name = maxstrlen(self.names)

        for n in sorted(self.names):
            chan = self[n]
            chan.reset_valid()
            inters = np.intersect1d(chan.pids, all_pids)
            n_inters = len(inters)

            if n_inters == n_all_pids and not show_complete:
                continue

            perc = percentage_missing(n_inters, n_all_pids)
            s_n_inters = str(n_inters).rjust(len_pids)
            s_perc = str(perc).rjust(len_perc)

            color = decide_color(n_inters, n_shared_pids, n_all_pids)
            cprint(chan.name.ljust(len_name), f"{s_n_inters} / {n_all_pids} -> {s_perc}% loss", dip(perc), color=color)

        print()
        color = decide_color(n_shared_pids, n_shared_pids, n_all_pids)
        cprint(f"over the whole data set: {n_shared_pids} / {n_all_pids} -> {max_perc}% loss", color=color)
        print_line()


    def reset_valid(self):
        channels = self.values()
        for chan in channels:
            chan.reset_valid()

    def save_names(self, fname, mode="x", **kwargs):
        with open(fname, mode=mode, **kwargs) as f:
            names = sorted(self.names)
            data = "\n".join(names)
            data += "\n" * 2
            f.writelines(data)

    def __getitem__(self, key):
        super_getitem = super().__getitem__
        if isinstance(key, str):
            return super_getitem(key)
        try:
            chans = {k: super_getitem(k) for k in key} #TODO: should subsetting copy channels (separate .valid)?
        except TypeError as e:
            raise KeyError(key) from e
        else:
            return SFData(chans)

    def __repr__(self):
        tn = typename(self)
        entries = len(self)
        return f"{tn}: {entries} channels"



