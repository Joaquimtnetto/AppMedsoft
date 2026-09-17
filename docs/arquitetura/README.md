# Arquitetura

```mermaid
flowchart LR
U[Usuário]-->B[Navegador]
B-->F[Flask]
F-->API[APIs]
API-->DB[(PostgreSQL)]
F-->TPL[Templates]
TPL-->B
```