{{/*
Common labels for all resources in this habitat
*/}}
{{- define "research-habitat.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
swarm.raphael.ai/habitat: {{ .Values.habitat.name }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "research-habitat.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
