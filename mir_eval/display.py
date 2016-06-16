# -*- encoding: utf-8 -*-
'''Display functions'''

import numpy as np
from scipy.signal import spectrogram

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
from matplotlib.ticker import FuncFormatter, MultipleLocator
from matplotlib.colors import LinearSegmentedColormap, LogNorm

from .melody import freq_to_voicing
from .util import midi_to_hz, hz_to_midi


def __expand_limits(ax, limits, which='x'):
    '''Helper function to expand axis limits'''

    if which == 'x':
        getter, setter = ax.get_xlim, ax.set_xlim
    elif which == 'y':
        getter, setter = ax.get_ylim, ax.set_ylim
    else:
        raise ValueError('invalid axis: {}'.format(which))

    old_lims = getter()
    new_lims = list(limits)

    # infinite limits occur on new axis objects with no data
    if np.isfinite(old_lims[0]):
        new_lims[0] = min(old_lims[0], limits[0])

    if np.isfinite(old_lims[1]):
        new_lims[1] = max(old_lims[1], limits[1])

    setter(new_lims)


def __get_axes(ax=None, fig=None):
    '''Get or construct the target axes object for a new plot.

    Parameters
    ----------
    ax : matplotlib.pyplot.axes, optional
        If provided, return this axes object directly.

    fig : matplotlib.figure.Figure, optional
        The figure to query for axes.
        By default, uses the current figure `plt.gcf()`.

    Returns
    -------
    ax : matplotlib.pyplot.axes
        An axis handle on which to draw the segmentation.
        If none is provided, a new set of axes is created.

    new_axes : bool
        If `True`, the axis object was newly constructed.
        If `False`, the axis object already existed.

    '''

    new_axes = False

    if ax is not None:
        return ax, new_axes

    if fig is None:
        fig = plt.gcf()

    if not fig.get_axes():
        new_axes = True

    return fig.gca(), new_axes


def segments(intervals, labels, base=None, height=None, text=False,
             text_kw=None, ax=None, **kwargs):
    '''Plot a segmentation as a set of disjoint rectangles.

    Parameters
    ----------
    intervals : np.ndarray, shape=(n, 2)
        segment intervals, in the format returned by
        :func:`mir_eval.io.load_intervals` or
        :func:`mir_eval.io.load_labeled_intervals`.

    labels : list, shape=(n,)
        reference segment labels, in the format returned by
        :func:`mir_eval.io.load_labeled_intervals`.

    base : number
        The vertical position of the base of the rectangles.
        By default, this will be the bottom of the plot.

    height : number
        The height of the rectangles.
        By default, this will be the top of the plot (minus `base`).

    text : bool
        If true, each segment's label is displayed in its
        upper-left corner

    text_kw : dict
        If `text==True`, the properties of the text
        object can be specified here.
        See `matplotlib.pyplot.Text` for valid parameters

    ax : matplotlib.pyplot.axes
        An axis handle on which to draw the segmentation.
        If none is provided, a new set of axes is created.

    kwargs
        Additional keyword arguments to pass to
        `matplotlib.patches.Rectangle`.

    Returns
    -------
    ax : matplotlib.pyplot.axes._subplots.AxesSubplot
        A handle to the (possibly constructed) plot axes
    '''
    if text_kw is None:
        text_kw = dict()
    text_kw.setdefault('va', 'top')
    text_kw.setdefault('clip_on', True)
    text_kw.setdefault('bbox', dict(boxstyle='round', facecolor='white'))

    seg_def_style = dict(linewidth=1)

    ax, new_axes = __get_axes(ax=ax)

    if new_axes:
        ax.set_ylim([0, 1])

    # Infer height
    if base is None:
        base = ax.get_ylim()[0]

    if height is None:
        height = ax.get_ylim()[1]

    cycler = ax._get_patches_for_fill.prop_cycler

    seg_map = dict()

    for lab in labels:
        if lab in seg_map:
            continue

        style = next(cycler)
        seg_map[lab] = seg_def_style.copy()
        seg_map[lab].update(style)
        # Swap color -> facecolor here so we preserve edgecolor on rects
        seg_map[lab]['facecolor'] = seg_map[lab].pop('color')
        seg_map[lab].update(kwargs)
        seg_map[lab]['label'] = lab

    for ival, lab in zip(intervals, labels):
        rect = Rectangle((ival[0], base), ival[1] - ival[0], height,
                         **seg_map[lab])
        ax.add_patch(rect)
        seg_map[lab].pop('label', None)

        if text:
            ann = ax.annotate(lab,
                              xy=(ival[0], height), xycoords='data',
                              xytext=(8, -10), textcoords='offset points',
                              **text_kw)
            ann.set_clip_path(rect)

    if new_axes:
        ax.set_yticks([])

    __expand_limits(ax, [intervals.min(), intervals.max()], which='x')

    return ax


def labeled_intervals(intervals, labels, label_set=None,
                      base=None, height=None, extend_labels=True,
                      ax=None, tick=True, **kwargs):
    '''Plot labeled intervals with each label on its own row.

    Parameters
    ----------
    intervals : np.ndarray, shape=(n, 2)
        segment intervals, in the format returned by
        :func:`mir_eval.io.load_intervals` or
        :func:`mir_eval.io.load_labeled_intervals`.

    labels : list, shape=(n,)
        reference segment labels, in the format returned by
        :func:`mir_eval.io.load_labeled_intervals`.

    label_set : list
        An (ordered) list of labels to determine the plotting order.
        If not provided, the labels will be inferred from
        `ax.get_yticklabels()`.
        If no `yticklabels` exist, then the sorted set of unique values
        in `labels` is taken as the label set.

    base : np.ndarray, shape=(n,), optional
        Vertical positions of each label.
        By default, labels are positioned at integers `np.arange(len(labels))`.

    height : scalar or np.ndarray, shape=(n,), optional
        Height for each label.
        If scalar, the same value is applied to all labels.
        By default, each label has `height=1`.

    extend_labels : bool
        If `False`, only values of `labels` that also exist in `label_set`
        will be shown.

        If `True`, all labels are shown, with those in `labels` but
        not in `label_set` appended to the top of the plot.
        A horizontal line is drawn to indicate the separation between
        values in or out of `label_set`.

    ax : matplotlib.pyplot.axes
        An axis handle on which to draw the intervals.
        If none is provided, a new set of axes is created.

    tick : bool
        If `True`, sets tick positions and labels on the y-axis.

    kwargs
        Additional keyword arguments to pass to
        `matplotlib.patches.Rectangle`.

    Returns
    -------
    ax : matplotlib.pyplot.axes._subplots.AxesSubplot
        A handle to the (possibly constructed) plot axes
    '''

    # Get the axes handle
    ax, _ = __get_axes(ax=ax)

    if label_set is None:
        # If we have non-empty pre-existing tick labels, use them
        label_set = [_.get_text() for _ in ax.get_yticklabels()]
        # If none of the label strings have content, treat it as empty
        if not any(label_set):
            label_set = []
    else:
        label_set = list(label_set)

    # Put additional labels at the end, in order
    if extend_labels:
        ticks = label_set + sorted(set(labels) - set(label_set))
    elif label_set:
        ticks = label_set
    else:
        ticks = sorted(set(labels))

    seg_def_style = dict(linewidth=1)

    seg_map = dict()
    seg_y = dict()

    style = next(ax._get_patches_for_fill.prop_cycler)
    if base is None:
        base = np.arange(len(ticks))

    if height is None:
        height = 1

    if np.isscalar(height):
        height = height * np.ones_like(base)

    for y0, yi, lab in zip(base, height, ticks):
        seg_map[lab] = dict(label=lab)
        seg_map[lab].update(seg_def_style)
        seg_map[lab].update(style)
        # Swap color->facecolor to preserve edge color on rects
        seg_map[lab]['facecolor'] = seg_map[lab].pop('color')
        seg_map[lab].update(kwargs)

        seg_y[lab] = (y0, yi)

    seen = set()
    for ival, lab in zip(intervals, labels):
        if lab not in seg_map:
            continue
        over_lab = seg_map[lab].get('label', lab)

        # If we've already seen this label, remove it
        # This way, it only appears once in the legend
        if over_lab in seen:
            seg_map[lab].pop('label', None)

        seen.add(over_lab)
        ax.add_patch(Rectangle((ival[0], seg_y[lab][0]),
                               ival[1] - ival[0],
                               seg_y[lab][1], **seg_map[lab]))

    # Draw a line separating the new labels from pre-existing labels
    if label_set != ticks:
        ax.axhline(len(label_set), color='k', alpha=0.5)

    if tick:
        ax.set_yticks([])
        ax.grid('on', axis='y')
        ax.set_ylim([0, len(ticks)])
        ax.set_yticks(base)
        ax.set_yticklabels(ticks, va='bottom')

    __expand_limits(ax, [intervals.min(), intervals.max()], which='x')

    return ax


def hierarchy(intervals_hier, labels_hier, levels=None, ax=None, **kwargs):
    '''Plot a hierarchical segmentation

    Parameters
    ----------
    intervals_hier : list of np.ndarray
        A list of segmentation intervals.  Each element should be
        an n-by-2 array of segment intervals, in the format returned by
        :func:`mir_eval.io.load_intervals` or
        :func:`mir_eval.io.load_labeled_intervals`.
        Segmentations should be ordered by increasing specificity.

    labels_hier : list of list-like
        A list of segmentation labels.  Each element should
        be a list of labels for the corresponding element in
        `intervals_hier`.

    levels : list of string
        Each element `levels[i]` is a label for the `i`th segmentation.
        This is typically used to denote the levels in a segment hierarchy.

    kwargs :
        Additional keyword arguments to `labeled_intervals`.

    Returns
    -------
    ax
        A handle to the matplotlib axes
    '''

    # This will break if a segment label exists in multiple levels
    if levels is None:
        levels = list(range(len(intervals_hier)))

    # Get the axes handle
    ax, _ = __get_axes(ax=ax)

    # Count the pre-existing patches
    n_patches = len(ax.patches)

    for ints, labs, key in zip(intervals_hier[::-1],
                               labels_hier[::-1],
                               levels[::-1]):
        labeled_intervals(ints, labs, label=key, ax=ax, **kwargs)

    # Reverse the patch ordering for anything we've added.
    # This way, intervals are listed in the legend from top to bottom
    ax.patches[n_patches:] = ax.patches[n_patches:][::-1]
    return ax


def events(times, labels=None, base=None, height=None, ax=None, text_kw=None,
           **kwargs):
    '''Plot event times as a set of vertical lines

    Parameters
    ----------
    times : np.ndarray, shape=(n,)
        event times, in the format returned by
        :func:`mir_eval.io.load_events` or
        :func:`mir_eval.io.load_labeled_events`.

    labels : list, shape=(n,), optional
        event labels, in the format returned by
        :func:`mir_eval.io.load_labeled_events`.

    base : number
        The vertical position of the base of the line.
        By default, this will be the bottom of the plot.

    height : number
        The height of the lines.
        By default, this will be the top of the plot (minus `base`).

    ax : matplotlib.pyplot.axes
        An axis handle on which to draw the segmentation.
        If none is provided, a new set of axes is created.

    text_kw : dict
        If `labels` is provided, the properties of the text
        objects can be specified here.
        See `matplotlib.pyplot.Text` for valid parameters

    kwargs
        Additional keyword arguments to pass to
        `matplotlib.pyplot.vlines`.

    Returns
    -------
    ax : matplotlib.pyplot.axes._subplots.AxesSubplot
        A handle to the (possibly constructed) plot axes
    '''
    if text_kw is None:
        text_kw = dict()
    text_kw.setdefault('va', 'top')
    text_kw.setdefault('clip_on', True)
    text_kw.setdefault('bbox', dict(boxstyle='round', facecolor='white'))

    # Get the axes handle
    ax, new_axes = __get_axes(ax=ax)

    # If we have fresh axes, set the limits
    if new_axes:
        ax.set_ylim([0, 1])

    # Infer height
    if base is None:
        base = ax.get_ylim()[0]

    if height is None:
        height = ax.get_ylim()[1]

    cycler = ax._get_patches_for_fill.prop_cycler

    style = next(cycler).copy()
    style.update(kwargs)

    lines = ax.vlines(times, base, height, **style)

    if labels:
        for path, lab in zip(lines.get_paths(), labels):
            ax.annotate(lab,
                        xy=(path.vertices[0][0], height),
                        xycoords='data',
                        xytext=(8, -10), textcoords='offset points',
                        **text_kw)

    if new_axes:
        ax.set_yticks([])

    __expand_limits(ax, [times.min(), times.max()], which='x')

    return ax


def pitch(times, frequencies, midi=False, unvoiced=False, ax=None, **kwargs):
    '''Visualize pitch contours

    Parameters
    ----------
    times : np.ndarray, shape=(n,)
        Sample times of frequencies

    frequencies : np.ndarray, shape=(n,)
        frequencies (in Hz) of the pitch contours.
        Voicing is indicated by sign (positive for voiced,
        non-positive for non-voiced).

    midi : bool
        If `True`, plot on a MIDI-numbered vertical axis.
        Otherwise, plot on a linear frequency axis.

    unvoiced : bool
        If `True`, unvoiced pitch contours are plotted and indicated
        by transparency.

        Otherwise, unvoiced pitch contours are omitted from the display.

    ax : matplotlib.pyplot.axes
        An axis handle on which to draw the intervals.
        If none is provided, a new set of axes is created.

    kwargs :
        Additional keyword arguments to `labeled_intervals`.

    Returns
    -------
    ax : matplotlib.pyplot.axes._subplots.AxesSubplot
        A handle to the (possibly constructed) plot axes
    '''

    ax, _ = __get_axes(ax=ax)

    # First, segment into contiguously voiced contours
    frequencies, voicings = freq_to_voicing(np.asarray(frequencies,
                                                       dtype=np.float))

    # Here are all the change-points
    v_changes = 1 + np.flatnonzero(voicings[1:] != voicings[:-1])
    v_changes = np.unique(np.concatenate([[0], v_changes, [len(voicings)]]))

    # Set up arrays of slices for voiced and unvoiced regions
    v_slices, u_slices = [], []
    for start, end in zip(v_changes, v_changes[1:]):
        idx = slice(start, end)
        # A region is voiced if its starting sample is voiced
        # It's unvoiced if none of the samples in the region are voiced.
        if voicings[start]:
            v_slices.append(idx)
        elif frequencies[idx].all():
            u_slices.append(idx)

    # Now we just need to plot the contour
    style = dict()
    style.update(next(ax._get_lines.prop_cycler))
    style.update(kwargs)

    if midi:
        idx = frequencies > 0
        frequencies[idx] = hz_to_midi(frequencies[idx])

        # Tick at integer midi notes
        ax.yaxis.set_minor_locator(MultipleLocator(1))

    for idx in v_slices:
        ax.plot(times[idx], frequencies[idx], **style)
        style.pop('label', None)

    # Plot the unvoiced portions
    if unvoiced:
        style['alpha'] = style.get('alpha', 1.0) * 0.5
        for idx in u_slices:
            ax.plot(times[idx], frequencies[idx], **style)

    return ax


def multipitch(times, frequencies, midi=False, unvoiced=False, ax=None,
               **kwargs):
    '''Visualize multiple f0 measurements

    Parameters
    ----------
    times : np.ndarray, shape=(n,)
        Sample times of frequencies

    frequencies : list of np.ndarray
        frequencies (in Hz) of the pitch measurements.
        Voicing is indicated by sign (positive for voiced,
        non-positive for non-voiced).

        `times` and `frequencies` should be in the format produced by
        :func:`mir_eval.io.load_ragged_time_series`

    midi : bool
        If `True`, plot on a MIDI-numbered vertical axis.
        Otherwise, plot on a linear frequency axis.

    unvoiced : bool
        If `True`, unvoiced pitches are plotted and indicated
        by transparency.

        Otherwise, unvoiced pitches are omitted from the display.

    ax : matplotlib.pyplot.axes
        An axis handle on which to draw the intervals.
        If none is provided, a new set of axes is created.

    kwargs :
        Additional keyword arguments to `plt.scatter`.

    Returns
    -------
    ax : matplotlib.pyplot.axes._subplots.AxesSubplot
        A handle to the (possibly constructed) plot axes
    '''

    # Get the axes handle
    ax, _ = __get_axes(ax=ax)

    # Set up a style for the plot
    style_voiced = dict()
    style_voiced.update(next(ax._get_lines.prop_cycler))
    style_voiced.update(kwargs)

    style_unvoiced = style_voiced.copy()
    style_unvoiced.pop('label', None)
    style_unvoiced['alpha'] = style_unvoiced.get('alpha', 1.0) * 0.5

    # We'll collect all times and frequencies first, then plot them
    voiced_times = []
    voiced_freqs = []

    unvoiced_times = []
    unvoiced_freqs = []

    for t, freqs in zip(times, frequencies):
        if not len(freqs):
            continue

        freqs, voicings = freq_to_voicing(np.asarray(freqs, dtype=np.float))

        # Discard all 0-frequency measurements
        idx = freqs > 0
        freqs = freqs[idx]
        voicings = voicings[idx]

        if midi:
            freqs = hz_to_midi(freqs)

        n_voiced = sum(voicings)
        voiced_times.extend([t] * n_voiced)
        voiced_freqs.extend(freqs[voicings])
        unvoiced_times.extend([t] * (len(freqs) - n_voiced))
        unvoiced_freqs.extend(freqs[~voicings])

    # Plot the voiced frequencies
    ax.scatter(voiced_times, voiced_freqs, **style_voiced)

    # Plot the unvoiced frequencies
    if unvoiced:
        ax.scatter(unvoiced_times, unvoiced_freqs, **style_unvoiced)

    # Tick at integer midi notes
    if midi:
        ax.yaxis.set_minor_locator(MultipleLocator(1))
    return ax


def piano_roll(intervals, pitches=None, midi=None, ax=None, **kwargs):
    '''Plot a quantized piano roll as intervals

    Parameters
    ----------
    intervals : np.ndarray, shape=(n, 2)
        timing intervals for notes

    pitches : np.ndarray, shape=(n,), optional
        pitches of notes (in Hz).

    midi : np.ndarray, shape=(n,), optional
        pitches of notes (in MIDI numbers).

        At least one of `pitches` or `midi` must be provided.

    ax : matplotlib.pyplot.axes
        An axis handle on which to draw the intervals.
        If none is provided, a new set of axes is created.

    kwargs :
        Additional keyword arguments to `labeled_intervals`.

    Returns
    -------
    ax : matplotlib.pyplot.axes._subplots.AxesSubplot
        A handle to the (possibly constructed) plot axes
    '''

    if midi is None:
        midi = hz_to_midi(pitches)

    scale = np.arange(128)
    ax = labeled_intervals(intervals, np.round(midi).astype(int),
                           label_set=scale,
                           tick=False,
                           ax=ax,
                           **kwargs)

    # Minor tick at each semitone
    ax.yaxis.set_minor_locator(MultipleLocator(1))

    ax.axis('auto')
    return ax


def separation(sources, fs=22050, labels=None, ax=None, **kwargs):
    '''Source-separation visualization

    Parameters
    ----------
    sources : list of np.ndarray
        A list of waveform buffers corresponding to each source

    fs : number > 0
        The sampling rate

    labels : list of strings
        An optional list of descriptors corresponding to each source

    ax : matplotlib.pyplot.axes
        An axis handle on which to draw the spectrograms.
        If none is provided, a new set of axes is created.

    kwargs :
        Additional keyword arguments to `scipy.signal.spectrogram`

    Returns
    -------
    ax
        The axis handle for this plot
    '''

    # Get the axes handle
    ax, _ = __get_axes(ax=ax)

    if labels is None:
        labels = ['Source {:d}'.format(_) for _ in range(len(sources))]

    kwargs.setdefault('scaling', 'spectrum')

    # The cumulative spectrogram across sources
    # is used to establish the reference power
    # for each individual source
    cumspec = None
    specs = []
    for i, src in enumerate(sources):
        freqs, times, spec = spectrogram(src, fs=fs, **kwargs)
        specs.append(spec)
        if cumspec is None:
            cumspec = spec.copy()
        else:
            cumspec += spec

    ref_max = cumspec.max()
    ref_min = ref_max * 1e-6

    legend_entries = []
    for i, spec in enumerate(specs):

        # For each source, grab a new color from the cycler
        # Then construct a colormap that interpolates from
        # [transparent white -> new color]
        color = next(ax._get_lines.prop_cycler)['color']
        cmap = LinearSegmentedColormap.from_list(labels[i],
                                                 [(1.0, 1.0, 1.0, 0.0),
                                                  color])

        ax.pcolormesh(times, freqs, spec,
                      cmap=cmap,
                      norm=LogNorm(vmin=ref_min, vmax=ref_max),
                      shading='gouraud',
                      label=labels[i])

        legend_entries.append(Patch(color=color, label=labels[i]))

    handles, legend_labels = ax.get_legend_handles_labels()
    handles.extend(legend_entries)
    legend_labels.extend(labels)

    ax.legend(handles=handles, labels=legend_labels)

    __expand_limits(ax, [times.min(), times.max()], which='x')
    __expand_limits(ax, [freqs.min(), freqs.max()], which='y')
    return ax


def __ticker_midi_note(x, pos):
    '''A ticker function for midi notes.

    Inputs x are interpreted as midi numbers, and converted
    to [NOTE][OCTAVE]+[cents].
    '''

    NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    idx = int(x % 12)
    cents = float(np.mod(x, 1.0))
    if cents >= 0.5:
        cents = cents - 1.0
        idx += 1

    octave = int(x // 12)

    if cents == 0:
        return '{:s}{:2d}'.format(NOTES[idx], octave)
    return '{:s}{:2d}{:+02d}'.format(NOTES[idx], octave, int(cents * 100))


def __ticker_midi_hz(x, pos):
    '''A ticker function for midi pitches.

    Inputs x are interpreted as midi numbers, and converted
    to Hz.
    '''

    return '{:g}'.format(midi_to_hz(x))


def ticker_notes(ax=None):
    '''Set the y-axis of the given axes to MIDI notes

    Parameters
    ----------
    ax : matplotlib.pyplot.axes
        The axes handle to apply the ticker.
        By default, uses the current axes handle.

    '''
    ax, _ = __get_axes(ax=ax)

    ax.yaxis.set_major_formatter(FMT_MIDI_NOTE)
    # Get the tick labels and reset the vertical alignment
    for tick in ax.yaxis.get_ticklabels():
        tick.set_verticalalignment('baseline')


def ticker_pitch(ax=None):
    '''Set the y-axis of the given axes to MIDI frequencies

    Parameters
    ----------
    ax : matplotlib.pyplot.axes
        The axes handle to apply the ticker.
        By default, uses the current axes handle.
    '''
    ax, _ = __get_axes(ax=ax)

    ax.yaxis.set_major_formatter(FMT_MIDI_HZ)


# Instantiate ticker objects; we don't need more than one of each
FMT_MIDI_NOTE = FuncFormatter(__ticker_midi_note)
FMT_MIDI_HZ = FuncFormatter(__ticker_midi_hz)
