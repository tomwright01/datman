#!/bin/bash

# master scriptit for FUNC: REST.
# generated: 2017/02/23 -- 17:32:48 by jviviano.

# datman script should accept the following arguments:
# rest.sh /path/to/data del_tr tr_length dims_isotropic
# therefore, it must be edited after rendering

DIR_MODULES=/archive/code/epitome/modules
DIR_DATA=/projects/jviviano/data/epitome
DIR_EXPT=TEMP
DATA_TYPE=FUNC
ID=datman_rest-sprl

fsrecon
init_basic high 4
deoblique func_del
motion_deskull func_ob loose FSL
despike func_deskull
calc_dvars func_despike
calc_censor func_despike 50.0 0.3 3.0
scale func_despike scale
linreg_calc_fsl high corratio 6
linreg_fs2epi_fsl
trscrub func_scaled 50 0.3 3 interp
filter func_scrubbed 2 diff off sq std gm off off 3
lowpass_freq func_filtered butterworth 0.1
nonlinreg_calc_fsl
linreg_epi2t1_fsl func_lowpass 3.0
nonlinreg_epi2mni_fsl func_lowpass 3.0
volsmooth func_MNI-nonlin 12.0 normal
