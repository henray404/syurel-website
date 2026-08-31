// Host tests for the pure logic headers. No Arduino, no hardware.
#include <cstdio>
#include <cmath>
#include <cstring>
#include "logic_median.h"
#include "logic_rain.h"
#include "logic_level.h"
#include "logic_csv.h"
#include "logic_height.h"

static int g_failures = 0;
static int g_checks = 0;

#define CHECK(cond, msg)                                                    \
  do {                                                                      \
    ++g_checks;                                                             \
    if (!(cond)) {                                                          \
      printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, msg);                  \
      ++g_failures;                                                         \
    }                                                                       \
  } while (0)

#define CHECK_NEAR(a, b, tol, msg) CHECK(fabs((a) - (b)) < (tol), msg)

static void test_median() {
  float a[5] = {5, 1, 3, 99, 2};
  CHECK_NEAR(medianOf(a, 5), 3.0f, 1e-6, "median ignores the outlier 99");

  float b[3] = {10, 10, 10};
  CHECK_NEAR(medianOf(b, 3), 10.0f, 1e-6, "constant input");

  float c[1] = {42};
  CHECK_NEAR(medianOf(c, 1), 42.0f, 1e-6, "single sample");

  CHECK(std::isnan(medianOf(NULL, 0)), "empty input is NAN, not 0");

  // The reason median beats mean here: one bad echo must not move the answer.
  float d[5] = {70, 71, 70, 400, 71};
  CHECK_NEAR(medianOf(d, 5), 71.0f, 1e-6, "one wild reflection does not shift the median");

  // Even-length input: v[n/2] is the UPPER of the two middle elements
  // (lower-mid=2, upper-mid=10, mean=6 -- all three would differ here).
  // This is the approved behaviour; the test documents it, not changes it.
  float e[4] = {1, 2, 10, 20};
  CHECK_NEAR(medianOf(e, 4), 10.0f, 1e-6, "even n returns the upper-middle element, not the lower-middle");
}

static void test_rain_window() {
  // WINDOW LENGTH COMES FROM config.h, NEVER FROM A LITERAL 60.
  //
  // These checks were written when RAIN_WINDOW_MIN was 60 and kept saying so
  // after it became 10, which is why three of them failed while the report
  // still claimed 47/47. RainWindow scales its total by 60/kBins, so both the
  // bin count AND the expected rate have to follow the constant.
  const int   BINS  = RAIN_WINDOW_MIN;
  const float SCALE = 60.0f / (float)RAIN_WINDOW_MIN;   // window total -> hourly rate

  RainWindow w;

  // One tip per bin, stopping one short of a wrap: the tips SUM, they are never
  // extrapolated from a single minute.
  for (int i = 0; i < BINS - 1; ++i) { w.addTips(1); w.advanceMinute(); }
  CHECK_NEAR(w.mmPerHour(0.30f), (float)(BINS - 1) * 0.30f * SCALE, 1e-4,
             "tips across the window sum, scaled once to an hourly rate");

  // The v1.4 bug this replaces: 2 tips in ONE minute extrapolated to 36 mm/h.
  // The result is now the window's rate, not one minute blown up by 60.
  RainWindow burst;
  burst.addTips(2);
  CHECK_NEAR(burst.mmPerHour(0.30f), 2.0f * 0.30f * SCALE, 1e-4,
             "a 2-tip burst is the window rate, not a one-minute extrapolation");

  // Bins older than the window must fall out of it.
  RainWindow old;
  old.addTips(100);
  for (int i = 0; i < BINS; ++i) old.advanceMinute();
  CHECK_NEAR(old.mmPerHour(0.30f), 0.0f, 1e-4,
             "tips older than RAIN_WINDOW_MIN leave the window");

  // lastMinuteTips reports the current bin, used for the tip_menit column.
  RainWindow cur;
  cur.addTips(3);
  CHECK(cur.lastMinuteTips() == 3, "current bin count");
  cur.advanceMinute();
  CHECK(cur.lastMinuteTips() == 0, "new bin starts empty");

  // Pin exactly which bin gets evicted, and exactly when. A known count sits in
  // bin 0; it must survive BINS-1 rotations (still inside the window) and be
  // cleared on the BINS-th, when head_ wraps back around to bin 0.
  RainWindow evict;
  evict.addTips(7);                                   // bin[0] = 7
  for (int i = 0; i < BINS - 1; ++i) evict.advanceMinute();
  CHECK_NEAR(evict.mmPerHour(1.0f), 7.0f * SCALE, 1e-4,
             "bin survives BINS-1 advances -- not yet older than the window");
  evict.advanceMinute();                               // the advance that wraps onto bin 0
  CHECK_NEAR(evict.mmPerHour(1.0f), 0.0f, 1e-4,
             "bin 0 is the one cleared exactly on the wrapping advance");
}

static void test_level_fsm() {
  // HEIGHTS ARE DERIVED FROM config.h, NEVER HARDCODED.
  //
  // This block used to spell the thresholds out as 30/60/25/55. When the rig's
  // working range was rescaled to 0-5 cm those literals silently stopped
  // matching config.h: 18 of the 47 checks failed while the report still
  // claimed all 47 passed. Deriving every height from the constants means the
  // next rescale carries these tests with it instead of leaving them behind.
  const float LOW     = WASPADA_EXIT - 0.5f;                      // safely AMAN
  const float MID_W   = (WASPADA_ENTER + WASPADA_EXIT) * 0.5f;    // inside WASPADA hysteresis
  const float OVER_W  = WASPADA_ENTER + 0.5f;                     // WASPADA, not yet BAHAYA
  const float JUST_W  = WASPADA_ENTER + 0.1f;                     // barely over the enter edge
  const float UNDER_W = WASPADA_ENTER - 0.1f;                     // barely under it, still above exit
  const float OVER_B  = BAHAYA_ENTER + 0.5f;                      // BAHAYA
  const float MID_B   = (BAHAYA_ENTER + BAHAYA_EXIT) * 0.5f;      // inside BAHAYA hysteresis
  const float UNDER_B = BAHAYA_EXIT - 0.1f;                       // under BAHAYA exit, over WASPADA enter

  // Escalation is immediate.
  LevelFsm f;
  CHECK(f.update(LOW, true, 0, 0) == AMAN, "starts safe");
  CHECK(f.update(OVER_W, true, 0, 1000) == WASPADA, "escalates immediately past WASPADA_ENTER");
  CHECK(f.update(OVER_B, true, 0, 2000) == BAHAYA, "escalates immediately past BAHAYA_ENTER");

  // De-escalation needs BOTH the exit threshold and the dwell time.
  LevelFsm g;
  g.update(OVER_W, true, 0, 0);                                // -> WASPADA
  CHECK(g.update(MID_W, true, 0, 1000) == WASPADA, "below enter but above exit: holds");
  CHECK(g.update(LOW, true, 0, 2000) == WASPADA, "below exit but dwell not met: holds");
  CHECK(g.update(LOW, true, 0, 70000) == AMAN, "below exit and dwell met: de-escalates");

  // The relay-chatter case: ripple around the threshold must not flip state.
  LevelFsm h;
  h.update(JUST_W, true, 0, 0);                                // -> WASPADA
  CHECK(h.update(UNDER_W, true, 0, 100000) == WASPADA,
        "just under enter is inside the hysteresis band");
  CHECK(h.update(JUST_W, true, 0, 200000) == WASPADA, "still WASPADA, no flip");

  // Invalid height must not cause de-escalation -- missing data is not evidence
  // of safety, and de-escalating would switch the pump off during a fault.
  // A single tick right after escalating is not enough to prove this: the
  // dwell timer hasn't expired yet, so even a buggy implementation that lets
  // invalid readings de-escalate would still show BAHAYA at that one tick.
  // Push a second invalid tick well past DWELL_DOWN_MS and confirm it is
  // STILL BAHAYA -- this is the assertion the mutation testing said mattered most.
  LevelFsm k;
  k.update(OVER_B, true, 0, 0);                                // -> BAHAYA
  CHECK(k.update(0, false, 0, 100000) == BAHAYA, "invalid reading holds the current level");
  CHECK(k.update(0, false, 0, 170000) == BAHAYA,
        "invalid reading STILL holds after DWELL_DOWN_MS has elapsed -- no de-escalation on bad data, ever");

  // Rain alone can raise the level even when the river is low. The height is
  // held safely under WASPADA_ENTER so only the rain term can be responsible.
  LevelFsm r;
  CHECK(r.update(LOW, true, RAIN_BAHAYA + 5.0f, 0) == BAHAYA, "heavy rain escalates on its own");

  // Rain strictly between RAIN_WASPADA and RAIN_BAHAYA must land on WASPADA,
  // not skip straight to BAHAYA or fall through to AMAN.
  LevelFsm r2;
  CHECK(r2.update(LOW, true, (RAIN_WASPADA + RAIN_BAHAYA) * 0.5f, 0) == WASPADA,
        "moderate rain between thresholds escalates to WASPADA only");

  CHECK(strcmp(LevelFsm::name(WASPADA), "WASPADA") == 0, "name mapping");

  // Hysteresis: BAHAYA exits at BAHAYA_EXIT, not at BAHAYA_ENTER. A height
  // strictly between the two -- below enter, at/above exit -- must hold BAHAYA
  // indefinitely. Only dropping below the exit may de-escalate, and that
  // transition lands on WASPADA: the BAHAYA -> WASPADA path.
  LevelFsm m;
  m.update(OVER_B, true, 0, 0);                                // -> BAHAYA
  CHECK(m.update(MID_B, true, 0, 10000) == BAHAYA, "below BAHAYA_ENTER but still holds BAHAYA");
  CHECK(m.update(MID_B, true, 0, 200000) == BAHAYA,
        "still holds BAHAYA long after, proving the exit edge is BAHAYA_EXIT, not BAHAYA_ENTER");
  m.update(UNDER_B, true, 0, 220000);                          // below exit: pending de-escalation
  CHECK(m.update(UNDER_B, true, 0, 280000) == WASPADA,
        "below BAHAYA_EXIT and dwell met: de-escalates to WASPADA (BAHAYA -> WASPADA path)");

  // Boundary values: enter thresholds are strict '>', exit thresholds are '>='.
  // Exactly ON each constant, which no other check above uses.
  LevelFsm b1;
  CHECK(b1.update(WASPADA_ENTER, true, 0, 0) == AMAN,
        "exactly at WASPADA_ENTER does not escalate -- enter is strict '>'");
  LevelFsm b2;
  CHECK(b2.update(BAHAYA_ENTER, true, 0, 0) == WASPADA,
        "exactly at BAHAYA_ENTER escalates only to WASPADA, not BAHAYA -- enter is strict '>'");
  LevelFsm b3;
  b3.update(OVER_W, true, 0, 0);                               // -> WASPADA
  CHECK(b3.update(WASPADA_EXIT, true, 0, 100000) == WASPADA,
        "exactly at WASPADA_EXIT still counts as WASPADA -- exit is '>=', not below it");
  LevelFsm b4;
  b4.update(OVER_B, true, 0, 0);                               // -> BAHAYA
  CHECK(b4.update(BAHAYA_EXIT, true, 0, 100000) == BAHAYA,
        "exactly at BAHAYA_EXIT still counts as BAHAYA -- exit is '>=', not below it");

  // millis() wraps every ~49.7 days. since_ starts 20000 ms before the wrap;
  // the dwell window must straddle the wrap and still resolve at the correct
  // elapsed time using unsigned modular subtraction, not signed arithmetic.
  const uint32_t t1 = 4294947296UL;                            // 2^32 - 20000
  LevelFsm w;
  w.update(OVER_W, true, 0, t1);                               // -> WASPADA
  w.update(LOW, true, 0, t1);                                  // below exit: pending=AMAN, since_=t1
  CHECK(w.update(LOW, true, 0, 10000UL) == WASPADA,
        "30000 ms after since_ (straddling the wrap): dwell not yet met, still holds");
  CHECK(w.update(LOW, true, 0, 50000UL) == AMAN,
        "70000 ms after since_ (straddling the wrap): dwell met, de-escalates at the right time");

  // current() must agree with what update() just returned -- a later task
  // reads current() directly for the CSV's flood-history columns.
  LevelFsm cc;
  Level ret = cc.update(OVER_B, true, 0, 0);
  CHECK(cc.current() == ret, "current() agrees with update()'s return value");

  // Catch the anti-pattern overflow in the dwell check: since_ + DWELL_DOWN_MS
  // can overflow uint32_t while now_ms hasn't wrapped yet. The WRONG code
  // (if (now_ms >= since_ + DWELL_DOWN_MS)) breaks when since_ + DWELL_DOWN_MS
  // overflows: 4294962295 + 60000 = 54999 after wrapping, so any now_ms > 54999
  // would incorrectly de-escalate even with <1000 ms elapsed. The CORRECT code
  // uses unsigned modular subtraction: (now_ms - since_ >= DWELL_DOWN_MS).
  const uint32_t ov_base = 0xFFFFFFFFUL - 5000;                  // 4294962295
  LevelFsm ov;
  ov.update(OVER_B, true, 0, ov_base);                           // -> BAHAYA
  ov.update(UNDER_B, true, 0, ov_base);                          // below exit: pending, since_=ov_base
  CHECK(ov.update(UNDER_B, true, 0, ov_base + 3000) == BAHAYA,
        "3000 ms elapsed (since_+DWELL_DOWN_MS overflows, but now_ms hasn't): holds BAHAYA");
  CHECK(ov.update(UNDER_B, true, 0, 59999UL) == WASPADA,
        "65000 ms elapsed (timestamp wrapped, but elapsed time computes correctly via modular subtraction): de-escalates");
}


static void test_csv() {
  LogRow r;
  r.ts_utc = "2026-08-15T07:04:00Z";
  r.ts_epoch = 1786518240UL;
  r.jarak_cm = 71.2f;
  r.tinggi_cm = 28.8f;
  r.valid = true;
  r.n_sampel = 12;
  r.tip_total = 145;
  r.tip_menit = 0;
  r.mm_per_jam = 0.0f;
  r.level = AMAN;
  r.pompa = 0;
  r.time_src = "rtc";
  r.rssi = -67;
  r.sms_status = "";

  char buf[256];
  int n = formatRow(buf, sizeof(buf), r);
  CHECK(n == (int)strlen(buf), "formatRow's return length equals the untruncated string length");
  CHECK(strcmp(buf,
        "2026-08-15T07:04:00Z,1786518240,71.2,28.8,1,12,145,0,0.0,AMAN,0,rtc,-67,\n") == 0,
        "row matches the documented schema exactly");

  // A second golden row with distinct, non-zero values in tip_menit, mm_per_jam
  // and pompa. The first golden row has all three at 0, so a column swap among
  // them would slip through undetected; this one pins each to its own column.
  LogRow r2;
  r2.ts_utc = "2026-08-15T08:00:00Z";
  r2.ts_epoch = 1786521600UL;
  r2.jarak_cm = 50.0f;
  r2.tinggi_cm = 50.0f;
  r2.valid = true;
  r2.n_sampel = 5;
  r2.tip_total = 200;
  r2.tip_menit = 7;
  r2.mm_per_jam = 4.5f;
  r2.level = WASPADA;
  r2.pompa = 1;
  r2.time_src = "ntp";
  r2.rssi = -50;
  r2.sms_status = "sent";
  char buf2[256];
  int n2 = formatRow(buf2, sizeof(buf2), r2);
  CHECK(strcmp(buf2,
        "2026-08-15T08:00:00Z,1786521600,50.0,50.0,1,5,200,7,4.5,WASPADA,1,ntp,-50,sent\n") == 0,
        "second golden row: tip_menit, mm_per_jam and pompa each land in their own column");
  (void)n2;

  // An invalid reading must still produce a row -- data with a known-bad flag is
  // usable, a missing row is a hole in the time series.
  r.valid = false;
  r.n_sampel = 0;
  n = formatRow(buf, sizeof(buf), r);
  CHECK(n == (int)strlen(buf), "invalid-row length matches what was actually written (not truncated)");
  CHECK(strstr(buf, ",0,0,145,") != NULL, "valid=0 and n_sampel=0 are recorded");

  // Capacity must be respected: a small cap must truncate, not overrun the
  // buffer. snprintf's return value is the length it WOULD have written, so it
  // must exceed strlen(buf) when truncated, and buf must still be terminated
  // within cap. sprintf swapped in for snprintf would not truncate at all.
  char small[20];
  int n3 = formatRow(small, sizeof(small), r);
  CHECK(n3 > (int)strlen(small), "formatRow reports the untruncated length, longer than what actually fit");
  CHECK(strlen(small) < sizeof(small), "buffer stays NUL-terminated within cap despite truncation");

  // Header column count must match the row column count, or every downstream
  // parse is silently misaligned.
  int header_commas = 0, row_commas = 0;
  for (const char *p = CSV_HEADER; *p; ++p) if (*p == ',') ++header_commas;
  for (const char *p = buf; *p; ++p) if (*p == ',') ++row_commas;
  CHECK(header_commas == row_commas, "header and row have the same column count");
}

// Every cross-module value elsewhere in this suite is a hand-typed literal.
// This feeds RainWindow's actual output into LevelFsm, so the composition of
// the two modules -- not just each in isolation -- is verified.
static void test_integration() {
  RainWindow rw;
  rw.addTips(120);                                    // 120 * 0.30 = 36.0 mm/h, > RAIN_BAHAYA(30)
  float mm_per_hour = rw.mmPerHour(MM_PER_TIP);

  LevelFsm fsm;
  Level lvl = fsm.update(5.0f, true, mm_per_hour, 0);  // river low, but rain alone is heavy
  CHECK(lvl == BAHAYA, "RainWindow's mmPerHour fed into LevelFsm::update yields BAHAYA from rain alone");
}


static void test_height() {
  // Distances are derived from the config constants, never written as literals:
  // JARAK_DASAR changes every time the sensor is remounted, and a suite that
  // hardcodes one mount goes red on a legitimate remount instead of on a bug.
  const float kWater = 3.0f;                                  // a plausible depth
  const float kNear  = JARAK_DASAR - kWater;                  // that much water
  const float kSlack = JARAK_DASAR + ULTRA_RANGE_SLACK_CM;    // last accepted
  CHECK(kNear > SENSOR_BLIND_CM, "test geometry: a 3 cm depth is outside the blind zone");

  // Speed-of-sound decode. These two numbers are quoted in config.h comments as
  // justification for SENSOR_BLIND_CM and ULTRA_ECHO_TIMEOUT_US; if the constant
  // ever changes, the comments become lies and this fails first.
  CHECK_NEAR(usToCm(1294), 22.0f, 0.1f, "ring-down 1294 us decodes to ~22 cm");
  CHECK_NEAR(usToCm(ULTRA_ECHO_TIMEOUT_US), 510.0f, 1.0f, "30 ms timeout is ~5 m of range");
  CHECK_NEAR(usToCm(0), 0.0f, 1e-6, "zero width is zero distance");

  // No echo at all is not a reading, and must never become a number.
  Ketinggian t = heightFrom(NULL, 0);
  CHECK(!t.valid && strcmp(t.reason, "timeout") == 0, "n=0 is timeout");
  CHECK(std::isnan(t.tinggi_cm), "timeout height is NAN, not 0");

  // Normal water.
  float mid[5] = {kNear, kNear, kNear - 0.1f, kNear + 0.1f, kNear};
  Ketinggian w = heightFrom(mid, 5);
  CHECK(w.valid && strcmp(w.reason, "") == 0, "a mid-range distance is a valid reading");
  CHECK_NEAR(w.tinggi_cm, kWater, 0.05f, "height is JARAK_DASAR minus the distance");

  // The blind-zone artefact. The module emits its own ring-down as an echo when
  // it hears nothing; at 22 cm that decoded to real water on a dry rig. This is
  // a property of the module, not of the mount, so 22.0 is a literal on purpose.
  CHECK(SENSOR_BLIND_CM > 22.0f, "the blind gate is above the 22 cm ring-down artefact");
  float ring[5] = {22.0f, 22.0f, 22.0f, 22.0f, 22.0f};
  Ketinggian r = heightFrom(ring, 5);
  CHECK(!r.valid && strcmp(r.reason, "too_close") == 0, "22 cm ring-down is rejected");
  CHECK(std::isnan(r.tinggi_cm), "too_close height is NAN, not a depth");

  // One wild ping must not move the verdict -- that is why this is a median.
  float spike[5] = {kNear, kNear, SENSOR_BLIND_CM - 20.0f, kNear + 0.1f, kNear - 0.1f};
  Ketinggian sp = heightFrom(spike, 5);
  CHECK(sp.valid, "a single wild outlier does not invalidate the reading");
  CHECK_NEAR(sp.tinggi_cm, kWater, 0.15f, "median ignores the outlier");

  // Over-range. This is the fix: at +20 cm slack a far reading clamped to 0 cm
  // of water with valid=1, and 0 reads as a dry bed -- the safest-looking number
  // the system can print, from an echo that is plainly wrong.
  float far[3] = {kSlack + 10.0f, kSlack + 10.0f, kSlack + 10.0f};
  Ketinggian f = heightFrom(far, 3);
  CHECK(!f.valid && strcmp(f.reason, "out_of_range") == 0, "well past the bed is rejected");
  CHECK(std::isnan(f.tinggi_cm), "out_of_range height is NAN, never 0");

  // Just past the bed is noise, not an error: an empty rig reading a little long
  // is still an empty rig, and clamping it to 0 is right.
  float bed[3] = {kSlack - 0.5f, kSlack - 0.5f, kSlack - 0.5f};
  Ketinggian b = heightFrom(bed, 3);
  CHECK(b.valid && strcmp(b.reason, "") == 0, "inside the slack is still a reading");
  CHECK_NEAR(b.tinggi_cm, 0.0f, 1e-6, "empty rig clamps to 0 cm, valid");

  // The gates must bracket the alert thresholds, or the sensor goes blind at a
  // level the FSM still has opinions about. This is what catches a remount that
  // puts the sensor too low to ever see BAHAYA.
  CHECK(JARAK_DASAR - SENSOR_BLIND_CM > BAHAYA_ENTER,
        "BAHAYA is reachable before the blind zone swallows the reading");
}

int main() {
  test_median();
  test_rain_window();
  test_level_fsm();
  test_csv();
  test_height();
  test_integration();
  printf("\n%d checks, %d failures\n", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
