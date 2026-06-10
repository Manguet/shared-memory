import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "embed", os.path.join(HERE, "..", "scripts", "embed.py"))
E = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E)


def fake_embed_fn(texts):
    """Vecteur déterministe 3D : longueur, nb 'a', nb 'e'. Suffisant pour la plomberie."""
    return [[float(len(t)), float(t.count("a")), float(t.count("e"))] for t in texts]


def fact(file, name, desc, body):
    return {"file": file, "name": name, "description": desc, "body": body, "path": file.split("/")[:-1]}


class StoreFreshnessTest(unittest.TestCase):
    def test_refresh_embeds_all_first_time(self):
        facts = [fact("d/a.md", "a", "da", "corps a"), fact("d/b.md", "b", "db", "corps b")]
        store = E.refresh_store(facts, {}, fake_embed_fn)
        self.assertEqual(set(store), {"d/a.md", "d/b.md"})
        self.assertIn("vec", store["d/a.md"])
        self.assertIn("hash", store["d/a.md"])

    def test_unchanged_fact_is_not_reembedded(self):
        facts = [fact("d/a.md", "a", "da", "corps a")]
        store = E.refresh_store(facts, {}, fake_embed_fn)
        calls = []
        def counting(texts):
            calls.append(texts); return fake_embed_fn(texts)
        store2 = E.refresh_store(facts, store, counting)
        self.assertEqual(calls, [])
        self.assertEqual(store2, store)

    def test_changed_body_triggers_reembed(self):
        facts = [fact("d/a.md", "a", "da", "corps a")]
        store = E.refresh_store(facts, {}, fake_embed_fn)
        facts[0]["body"] = "corps a modifié"
        store2 = E.refresh_store(facts, store, fake_embed_fn)
        self.assertNotEqual(store2["d/a.md"]["hash"], store["d/a.md"]["hash"])

    def test_deleted_fact_drops_from_store(self):
        facts = [fact("d/a.md", "a", "da", "x"), fact("d/b.md", "b", "db", "y")]
        store = E.refresh_store(facts, {}, fake_embed_fn)
        store2 = E.refresh_store(facts[:1], store, fake_embed_fn)
        self.assertEqual(set(store2), {"d/a.md"})

    def test_save_then_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "index.json")
            store = {"d/a.md": {"hash": "h", "vec": [1.0, 2.0]}}
            E.save_store(path, store)
            self.assertEqual(E.load_store(path), store)

    def test_load_missing_store_is_empty(self):
        self.assertEqual(E.load_store("/no/such/store.json"), {})


class CosineTopkTest(unittest.TestCase):
    def test_cosine_identical_is_one(self):
        self.assertAlmostEqual(E.cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0, places=6)

    def test_cosine_orthogonal_is_zero(self):
        self.assertAlmostEqual(E.cosine([1.0, 0.0], [0.0, 1.0]), 0.0, places=6)

    def test_cosine_zero_vector_is_zero(self):
        self.assertEqual(E.cosine([0.0, 0.0], [1.0, 1.0]), 0.0)

    def test_topk_orders_by_score_and_limits(self):
        store = {
            "a": {"vec": [1.0, 0.0]},
            "b": {"vec": [0.9, 0.1]},
            "c": {"vec": [0.0, 1.0]},
        }
        top = E.semantic_topk([1.0, 0.0], store, k=2)
        self.assertEqual([f for f, _ in top], ["a", "b"])
        self.assertEqual(len(top), 2)


if __name__ == "__main__":
    unittest.main()
