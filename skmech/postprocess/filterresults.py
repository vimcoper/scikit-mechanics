"""filter results for plotting"""
import numpy as np


def results_at_fixed_y(u, y=0, decimals=3):
    """filter results for a fixed y coordinate

    Args:
        u (numpy array): shape (num_nodes, 4) with format
            [x, y, field_x, field_y].
        y (float, default=0.): y coordinate to filter results
        decimals (int, default=1): number of decimals to approximate
            results at. Example: decilamel=1 implies finding nodes
            coordinates which y=0 +- 0.1.

    Returns:
        filtered_u (numpy array) same shape as u

    """
    # nodes where y = 0
    nodes_index = np.where(np.round(u[:, 1], decimals) == y)[0]
    filtered_u = u[nodes_index]
    # sort filtered_u based on x coordinate
    filtered_u = filtered_u[np.argsort(filtered_u[:, 0])]
    return filtered_u


def dict2array(u, nodes):
    """Convert dictionary to array

    Parameters
    ----------
    u : dict
        dictionary with node index and its displacement
    nodes : dict
        dictionary with node index and its location coordinates

    Returns
    -------
    numpy array
        numpy array with [x, y, ux, uy]

    """
    u_array = np.empty((len(u), 4))
    for i, (nid, [ux, uy]) in enumerate(u.items()):
        u_array[i] = [nodes[nid][0], nodes[nid][1], ux, uy]
    return u_array


if __name__ == '__main__':
    u = {0: [10, 20], 2: [1.1, 2.2]}
    nodes = {0: [0, 0], 2: [0, 1]}
    uar = dict2array(u, nodes)
    print(uar)
