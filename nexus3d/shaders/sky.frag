#version 150

uniform vec4 u_top_color;
uniform vec4 u_horizon_color;
uniform vec4 u_bottom_color;
uniform vec4 u_sun_color;
uniform vec4 u_sun_dir;
uniform float u_star_strength;
uniform float u_cloud_strength;
uniform float u_cloud_speed;
uniform float u_haze_strength;
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

float fbm(vec2 p) {
    float total = 0.0;
    float amplitude = 0.52;
    mat2 rot = mat2(0.82, -0.57, 0.57, 0.82);
    for (int i = 0; i < 5; ++i) {
        total += valueNoise(p) * amplitude;
        p = rot * p * 2.03 + vec2(3.1, -1.7);
        amplitude *= 0.5;
    }
    return total;
}

void main() {
    vec3 dir = normalize(v_local);
    float vertical = clamp(dir.z * 0.5 + 0.5, 0.0, 1.0);

    // Atmospheric base gradient with a denser horizon scattering band.
    float horizonMix = smoothstep(0.02, 0.58, vertical);
    vec3 lowColor = mix(u_bottom_color.rgb, u_horizon_color.rgb, horizonMix);
    vec3 color = mix(lowColor, u_top_color.rgb, smoothstep(0.39, 1.0, vertical));

    float horizonDistance = 1.0 - abs(dir.z);
    float haze = pow(max(horizonDistance, 0.0), 4.5) * u_haze_strength;
    color = mix(color, u_horizon_color.rgb * 1.18, clamp(haze, 0.0, 0.65));

    vec3 sunDir = normalize(u_sun_dir.xyz);
    float sunDot = max(dot(dir, sunDir), 0.0);
    float sunCore = pow(sunDot, 1200.0);
    float sunInner = pow(sunDot, 150.0) * 0.70;
    float sunHalo = pow(sunDot, 18.0) * 0.28;
    float forwardScatter = pow(sunDot, 5.0) * haze * 0.55;
    color += u_sun_color.rgb * (sunCore * 6.5 + sunInner + sunHalo + forwardScatter);

    // Two cloud layers moving at slightly different speeds create parallax.
    float t = u_time * 0.0040 * u_cloud_speed;
    vec2 projected = dir.xy / max(0.16, 0.40 + dir.z * 0.72);
    vec2 uvA = projected * 1.75 + vec2(t, -t * 0.58);
    vec2 uvB = projected * 3.05 + vec2(-t * 0.42, t * 0.25);
    float cloudA = fbm(uvA);
    float cloudB = fbm(uvB + cloudA * 0.55);
    float cloudShape = cloudA * 0.63 + cloudB * 0.37;
    float cloud = smoothstep(0.49, 0.72, cloudShape);
    cloud *= u_cloud_strength * smoothstep(0.18, 0.64, vertical);

    float cloudLight = 0.58 + pow(sunDot, 3.0) * 1.20;
    vec3 cloudColor = mix(color * 0.72, vec3(0.95, 0.98, 1.04) * cloudLight, 0.55);
    color = mix(color, cloudColor, cloud * 0.53);

    // Thin silver lining around sun-facing cloud edges.
    float edgeNoise = abs(cloudA - cloudB);
    float silver = smoothstep(0.16, 0.02, edgeNoise) * cloud * pow(sunDot, 7.0);
    color += u_sun_color.rgb * silver * 0.42;

    vec2 starProjection = dir.xy / max(0.10, abs(dir.z) + 0.26);
    vec2 starCell = floor(starProjection * 460.0);
    float starRnd = hash21(starCell);
    float star = step(0.9970, starRnd) * u_star_strength * smoothstep(0.47, 0.82, vertical);
    star *= 1.0 - cloud * 0.82;
    float twinkle = 0.70 + 0.30 * sin(u_time * (1.35 + starRnd * 2.4) + starRnd * 53.0);
    color += vec3(star * twinkle);

    // Slight filmic shoulder keeps very bright sun pixels from looking flat.
    color = color / (vec3(1.0) + color * 0.14);
    float zenithVignette = 0.955 + 0.045 * vertical;
    p3d_FragColor = vec4(color * zenithVignette, 1.0);
}
