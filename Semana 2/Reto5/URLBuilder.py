from urllib.parse import urljoin, quote, urlencode

class URLBuilder:
    def __init__(self, base_url: str):
        if not base_url.endswith('/'):
            base_url += '/'
        self.base_url = base_url

    def build_path(self, *path_segments) -> str:
        """Construye URLs escapando correctamente los parámetros (evita Path Traversal)"""
        # Validar y escapar cada segmento
        escaped_segments = [quote(str(segment), safe="") for segment in path_segments]
        path = "/".join(escaped_segments)
        return urljoin(self.base_url, path)

    def build_with_query(self, query_params: dict, *path_segments) -> str:
        """Construye URL con Query Params de forma segura"""
        base = self.build_path(*path_segments)
        if query_params:
            # urlencode escapa los caracteres peligrosos en query
            query_string = urlencode(query_params)
            return f"{base}?{query_string}"
        return base

# Pruebas integradas de seguridad:
builder = URLBuilder("http://localhost:3000/api/")

# Caso 1: Path Traversal (Usuario inyecta ../)
id_malicioso = "../../../etc/passwd"
# Lo que construiría el builder seguro: http://localhost:3000/api/productos/..%2F..%2F..%2Fetc%2Fpasswd
# (El servidor no saltará de directorio porque los slashes se codificaron).

# Caso 2: Inyección de Query Params en el path
id_query = "42?categoria=hack"
# Seguro: http://localhost:3000/api/productos/42%3Fcategoria%3Dhack 

# Caso 3: Caracteres raros/unicode
id_unicode = "id_con_espacios y 💀"
# Seguro: http://localhost:3000/api/productos/id_con_espacios%20y%20%F0%9F%92%80