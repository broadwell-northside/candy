shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float wet = smoothstep(3.0, -0.4, world_pos.z);
	vec3 dry = vec3(0.79, 0.67, 0.46);
	vec3 damp = vec3(0.52, 0.42, 0.31);
	ALBEDO = mix(dry, damp, wet);
	ROUGHNESS = mix(0.94, 0.42, wet);
	METALLIC = 0.0;
}
