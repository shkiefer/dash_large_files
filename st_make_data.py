import numpy as np
n_lines = 5000000
n = np.arange(0, n_lines)
om = np.pi / (n_lines/10.) * n
y1 = np.sin(om)
y2 = np.cos(2. * om)
lines = [f'{{"omega": {om[i]}, "y1": {y1[i]}, "y2": {y2[i]}}}\n' for i in n]
with open(f'my_data_{n_lines}.txt', 'w') as f:
    f.writelines(lines)


