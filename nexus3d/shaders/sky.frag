#version 150

uniform vec4 u_top_color;
uniform vec4 u_horizon_color;
uniform vec4 u_bottom_color;
uniform vec4 u_sun_color;
uniform vec4 u_sun_dir;
uniform float u_star_strength;
uniform float u_cloud_strength;
uniform float u_time;

in vec3 v_local;
out vec4 p3d_FragColor;

float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float valueNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void main() {
    vec3 dir = normalize(v_local);
    float vertical = clamp(dir.z * 0.5 + 0.5, 0.0, 1.0);
    float horizonBand = smoothstep(0.0, 0.52, vertical);
    vec3 lowColor = mix(u_bottom_color.rgb, u_horizon_color.rgb, horizonBand);
    vec3 color = mix(lowColor, u_top_color.rgb, smoothstep(0.42, 1.0, vertical));

    vec3 sunDir = normalize(u_sun_dir.xyz);
    float sunDot = max(dot(dir, sunDir), 0.0);
    float sunCore = pow(sunDot, 850.0);
    float sunHalo = pow(sunDot, 24.0) * 0.35;
    color += u_sun_color.rgb * (sunCore * 5.0 + sunHalo);

    vec2 cloudUv = dir.xy * 3.6 + vec2(u_time * 0.0025, -u_time * 0.0018);
    float cloud = valueNoise(cloudUv * 2.0) * 0.58 + valueNoise(cloudUv * 4.2) * 0.28 + valueNoise(cloudUv * 8.8) * 0.14;
    cloud = smoothstep(0.48, 0.78, cloud) * u_cloud_strength * smoothstep(0.20, 0.68, vertical);
    color = mix(color, color * 1.45 + vec3(0.03, 0.04, 0.055), cloud * 0.35);

    vec2 starCell = floor((dir.xy / max(0.08, abs(dir.z) + 0.28)) * 420.0);
    float starRnd = hash21(starCell);
    float star = step(0.9968, starRnd) * u_star_strength * smoothstep(0.48, 0.82, vertical);
    float twinkle = 0.72 + 0.28 * sin(u_time * (1.6 + starRnd * 2.0) + starRnd * 47.0);
    color += vec3(star * twinkle);

    float vignette = 0.96 + 0.04 * vertical;
    p3d_FragColor = vec4(color * vignette, 1.0);
}
