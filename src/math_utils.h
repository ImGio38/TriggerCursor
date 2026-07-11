#ifndef MATH_UTILS_H
#define MATH_UTILS_H

#include <cmath>

#if defined(__x86_64__) || defined(_M_X64) || defined(__i386__) || defined(_M_IX86)
#include <xmmintrin.h> // For SSE intrinsics (_mm_rsqrt_ss)
#define USE_SSE_INTRINSICS 1
#else
#define USE_SSE_INTRINSICS 0
#endif

namespace MathUtils {

    // Fast reciprocal square root (1 / sqrt(x))
    inline float FastInvSqrt(float x) {
#if USE_SSE_INTRINSICS
        __m128 src = _mm_set_ss(x);
        __m128 res = _mm_rsqrt_ss(src);
        float inv_mag = _mm_cvtss_f32(res);
        // One iteration of Newton-Raphson refinement for higher accuracy
        return inv_mag * (1.5f - 0.5f * x * inv_mag * inv_mag);
#else
        return 1.0f / std::sqrt(x);
#endif
    }

    /**
     * @brief Processes joystick raw inputs to apply a squared deadzone filter and a cubic response curve.
     * 
     * @param raw_x Raw X axis deflection (normalized to [-1.0f, 1.0f])
     * @param raw_y Raw Y axis deflection (normalized to [-1.0f, 1.0f])
     * @param deadzone Deadzone radius threshold (between 0.0f and 1.0f)
     * @param sensitivity Scale factor for cursor speed
     * @param curve_power Exponential factor for mouse acceleration (e.g. 1.0 = linear, 2.0 = quadratic, 3.0 = cubic)
     * @param out_dx Output horizontal speed (pixels)
     * @param out_dy Output vertical speed (pixels)
     */
    inline void ProcessJoystick(float raw_x, float raw_y, float deadzone, float sensitivity, float curve_power, float& out_dx, float& out_dy) {
        float mag2 = raw_x * raw_x + raw_y * raw_y;
        float deadzone2 = deadzone * deadzone;

        // 1. Squared Deadzone Filter (Zero overhead path for idle/centered joystick)
        if (mag2 < deadzone2) {
            out_dx = 0.0f;
            out_dy = 0.0f;
            return;
        }

        // 2. Normalize and apply response curve.
        // Use fast reciprocal square root to calculate 1/magnitude.
        float inv_mag = FastInvSqrt(mag2);
        float mag = mag2 * inv_mag; // mag = mag2 / sqrt(mag2) = sqrt(mag2)

        // Map magnitude to [0.0f, 1.0f] starting from the deadzone boundary
        float norm_mag = (mag - deadzone) / (1.0f - deadzone);
        if (norm_mag > 1.0f) norm_mag = 1.0f;
        if (norm_mag < 0.0f) norm_mag = 0.0f;

        // Apply customized power curve
        float accel_mag = std::pow(norm_mag, curve_power);

        // Final output speed = Direction * Accelerated Magnitude * Sensitivity
        // Out = (RawVector * inv_mag) * accel_mag * sensitivity
        float scale = accel_mag * inv_mag * sensitivity;
        
        out_dx = raw_x * scale;
        out_dy = raw_y * scale;
    }

} // namespace MathUtils

#endif // MATH_UTILS_H
