#ifndef CDD_DHT11_H
#define CDD_DHT11_H

#include "std_types.h"

/* DHT11 measurement snapshot */
typedef struct {
    float32 temperature_c;   /* [degC] */
    float32 humidity_pct;    /* [%RH] */
    uint32  ok_count;        /* number of valid frames (checksum OK) */
    uint32  err_count;       /* number of failed frames (timeout / checksum) */
    boolean valid;           /* TRUE once at least one valid frame received */
} Cdd_Dht11_DataType;

Std_ReturnType Cdd_Dht11_Init(void);
/* Called at the END of every 10 ms RTE tick: gives the DHT11 thread a
 * jitter-free window (~9 ms) to sample the 40-bit frame without colliding
 * with the real-time control task. */
void Cdd_Dht11_TickSync(void);
void Cdd_Dht11_GetLatest(Cdd_Dht11_DataType *data);

#endif /* CDD_DHT11_H */
