#ifndef CDD_L298N_H
#define CDD_L298N_H

#include "std_types.h"

/* L298N H-Bridge Direction Enumeration */
typedef enum {
    L298N_DIR_COAST   = 0,
    L298N_DIR_FORWARD = 1,
    L298N_DIR_REVERSE = 2,
    L298N_DIR_BRAKE   = 3
} Cdd_L298n_DirType;

/* CDD L298N Service Functions */
Std_ReturnType Cdd_L298n_Init(void);
Std_ReturnType Cdd_L298n_SetCommand(Cdd_L298n_DirType Direction, float32 DutyPercent);
void Cdd_L298n_EmergencyStop(void);

#endif /* CDD_L298N_H */
