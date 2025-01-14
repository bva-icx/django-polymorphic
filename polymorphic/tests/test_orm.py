import re
import uuid

from unittest import expectedFailure
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Case, Count, FilteredRelation, Q, When, F, Prefetch

from django.db.utils import IntegrityError
from django.test import TransactionTestCase
from polymorphic import compat, query_translate
from polymorphic.managers import PolymorphicManager
from polymorphic.models import PolymorphicTypeInvalid, PolymorphicTypeUndefined
from polymorphic.tests.models import (
    AliasOfNonProxyChild,
    AliasProxyChild,
    AltChildAsBaseModel,
    AltChildModel,
    AltChildWithM2MModel,
    ArtProject,
    Base,
    BlogA,
    BlogB,
    BlogBase,
    BlogEntry,
    BlogEntry_limit_choices_to,
    ChildModel,
    ChildModelWithManager,
    CustomPkBase,
    CustomPkInherit,
    Duck,
    Enhance_Base,
    Enhance_Inherit,
    InitTestModelSubclass,
    Model2A,
    Model2B,
    Model2C,
    Model2D,
    ModelExtraA,
    ModelExtraB,
    ModelExtraC,
    ModelExtraExternal,
    ModelFieldNameTest,
    ModelShow1,
    ModelShow1_plain,
    ModelShow2,
    ModelShow2_plain,
    ModelShow3,
    ModelUnderRelChild,
    ModelUnderRelParent,
    ModelWithMyManager,
    ModelWithMyManager2,
    ModelWithMyManagerDefault,
    ModelWithMyManagerNoDefault,
    ModelX,
    ModelY,
    MRODerived,
    MultiTableDerived,
    MyManager,
    MyManagerQuerySet,
    NonAliasNonProxyChild,
    NonPolymorphicParent,
    NonProxyChild,
    NonSymRelationA,
    NonSymRelationB,
    NonSymRelationBase,
    NonSymRelationBC,
    One2OneRelatingModel,
    One2OneRelatingModelDerived,
    ParentModel,
    ParentModelWithManager,
    PlainA,
    PlainB,
    PlainC,
    PlainChildModelWithManager,
    PlainModel,
    PlainModelWithM2M,
    PlainMyManager,
    PlainMyManagerQuerySet,
    PlainParentModelWithManager,
    ProxiedBase,
    ProxyBase,
    ProxyChild,
    ProxyChildAliasProxy,
    ProxyModelA,
    ProxyModelB,
    ProxyModelBase,
    RedheadDuck,
    RelatingModel,
    RelationA,
    RelationB,
    RelationBase,
    RelationBC,
    RubberDuck,
    SubclassSelectorAbstractBaseModel,
    SubclassSelectorAbstractConcreteModel,
    SubclassSelectorProxyBaseModel,
    SubclassSelectorProxyConcreteModel,
    TestParentLinkAndRelatedName,
    TradProxyOnProxyChild,
    TradProxyChild,
    UUIDArtProject,
    UUIDPlainA,
    UUIDPlainB,
    UUIDPlainC,
    UUIDProject,
    UUIDResearchProject,
)


class PolymorphicTests(TransactionTestCase):
    """
    The test suite
    """

    def test_annotate_aggregate_order(self):
        # create a blog of type BlogA
        # create two blog entries in BlogA
        # create some blogs of type BlogB to make the BlogBase table data really polymorphic
        blog = BlogA.objects.create(name="B1", info="i1")
        blog.blogentry_set.create(text="bla")
        BlogEntry.objects.create(blog=blog, text="bla2")
        BlogB.objects.create(name="Bb1")
        BlogB.objects.create(name="Bb2")
        BlogB.objects.create(name="Bb3")

        qs = BlogBase.objects.annotate(entrycount=Count("BlogA___blogentry"))
        self.assertEqual(len(qs), 4)

        for o in qs:
            if o.name == "B1":
                self.assertEqual(o.entrycount, 2)
            else:
                self.assertEqual(o.entrycount, 0)

        x = BlogBase.objects.aggregate(entrycount=Count("BlogA___blogentry"))
        self.assertEqual(x["entrycount"], 2)

        # create some more blogs for next test
        BlogA.objects.create(name="B2", info="i2")
        BlogA.objects.create(name="B3", info="i3")
        BlogA.objects.create(name="B4", info="i4")
        BlogA.objects.create(name="B5", info="i5")

        # test ordering for field in all entries
        expected = """
[ <BlogB: id 4, name (CharField) "Bb3">,
  <BlogB: id 3, name (CharField) "Bb2">,
  <BlogB: id 2, name (CharField) "Bb1">,
  <BlogA: id 8, name (CharField) "B5", info (CharField) "i5">,
  <BlogA: id 7, name (CharField) "B4", info (CharField) "i4">,
  <BlogA: id 6, name (CharField) "B3", info (CharField) "i3">,
  <BlogA: id 5, name (CharField) "B2", info (CharField) "i2">,
  <BlogA: id 1, name (CharField) "B1", info (CharField) "i1"> ]"""
        x = "\n" + repr(BlogBase.objects.order_by("-name"))
        self.assertEqual(x, expected)

        # test ordering for field in one subclass only
        # MySQL and SQLite return this order
        expected1 = """
[ <BlogA: id 8, name (CharField) "B5", info (CharField) "i5">,
  <BlogA: id 7, name (CharField) "B4", info (CharField) "i4">,
  <BlogA: id 6, name (CharField) "B3", info (CharField) "i3">,
  <BlogA: id 5, name (CharField) "B2", info (CharField) "i2">,
  <BlogA: id 1, name (CharField) "B1", info (CharField) "i1">,
  <BlogB: id 2, name (CharField) "Bb1">,
  <BlogB: id 3, name (CharField) "Bb2">,
  <BlogB: id 4, name (CharField) "Bb3"> ]"""

        # PostgreSQL returns this order
        expected2 = """
[ <BlogB: id 2, name (CharField) "Bb1">,
  <BlogB: id 3, name (CharField) "Bb2">,
  <BlogB: id 4, name (CharField) "Bb3">,
  <BlogA: id 8, name (CharField) "B5", info (CharField) "i5">,
  <BlogA: id 7, name (CharField) "B4", info (CharField) "i4">,
  <BlogA: id 6, name (CharField) "B3", info (CharField) "i3">,
  <BlogA: id 5, name (CharField) "B2", info (CharField) "i2">,
  <BlogA: id 1, name (CharField) "B1", info (CharField) "i1"> ]"""

        x = "\n" + repr(BlogBase.objects.order_by("-BlogA___info"))
        self.assertTrue(x == expected1 or x == expected2)

    def test_limit_choices_to(self):
        """
        this is not really a testcase, as limit_choices_to only affects the Django admin
        """
        # create a blog of type BlogA
        blog_a = BlogA.objects.create(name="aa", info="aa")
        blog_b = BlogB.objects.create(name="bb")
        # create two blog entries
        entry1 = BlogEntry_limit_choices_to.objects.create(blog=blog_b, text="bla2")
        entry2 = BlogEntry_limit_choices_to.objects.create(blog=blog_b, text="bla2")

    def test_primary_key_custom_field_problem(self):
        """
        object retrieval problem occuring with some custom primary key fields (UUIDField as test case)
        """
        UUIDProject.objects.create(topic="John's gathering")
        UUIDArtProject.objects.create(topic="Sculpting with Tim", artist="T. Turner")
        UUIDResearchProject.objects.create(topic="Swallow Aerodynamics", supervisor="Dr. Winter")

        qs = UUIDProject.objects.all()
        list(qs)
        a = qs[0]
        b = qs[1]
        c = qs[2]
        self.assertEqual(len(qs), 3)
        self.assertIsInstance(a.uuid_primary_key, uuid.UUID)
        self.assertIsInstance(a.pk, uuid.UUID)

        res = re.sub(' "(.*?)..", topic', ", topic", repr(qs))
        res_exp = """[ <UUIDProject: uuid_primary_key (UUIDField/pk), topic (CharField) "John's gathering">,
  <UUIDArtProject: uuid_primary_key (UUIDField/pk), topic (CharField) "Sculpting with Tim", artist (CharField) "T. Turner">,
  <UUIDResearchProject: uuid_primary_key (UUIDField/pk), topic (CharField) "Swallow Aerodynamics", supervisor (CharField) "Dr. Winter"> ]"""
        self.assertEqual(res, res_exp)

        a = UUIDPlainA.objects.create(field1="A1")
        b = UUIDPlainB.objects.create(field1="B1", field2="B2")
        c = UUIDPlainC.objects.create(field1="C1", field2="C2", field3="C3")
        qs = UUIDPlainA.objects.all()
        # Test that primary key values are valid UUIDs
        self.assertEqual(uuid.UUID("urn:uuid:%s" % a.pk, version=1), a.pk)
        self.assertEqual(uuid.UUID("urn:uuid:%s" % c.pk, version=1), c.pk)

    def create_model2abcd(self):
        """
        Create the chain of objects of Model2,
        this is reused in various tests.
        """
        a = Model2A.objects.create(field1="A1")
        b = Model2B.objects.create(field1="B1", field2="B2")
        c = Model2C.objects.create(field1="C1", field2="C2", field3="C3")
        d = Model2D.objects.create(field1="D1", field2="D2", field3="D3", field4="D4")

        return a, b, c, d

    def test_simple_inheritance(self):
        self.create_model2abcd()

        objects = Model2A.objects.all()
        self.assertQuerysetEqual(
            objects,
            [Model2A, Model2B, Model2C, Model2D],
            transform=lambda o: o.__class__,
            ordered=False,
        )

    def test_defer_fields(self):
        self.create_model2abcd()

        objects_deferred = Model2A.objects.defer("field1").order_by("id")

        self.assertNotIn(
            "field1",
            objects_deferred[0].__dict__,
            "field1 was not deferred (using defer())",
        )

        # Check that we have exactly one deferred field ('field1') per resulting object.
        for obj in objects_deferred:
            deferred_fields = obj.get_deferred_fields()
            self.assertEqual(1, len(deferred_fields))
            self.assertIn("field1", deferred_fields)

        objects_only = Model2A.objects.only("pk", "polymorphic_ctype", "field1")

        self.assertIn(
            "field1",
            objects_only[0].__dict__,
            'qs.only("field1") was used, but field1 was incorrectly deferred',
        )
        self.assertIn(
            "field1",
            objects_only[3].__dict__,
            'qs.only("field1") was used, but field1 was incorrectly deferred' " on a child model",
        )
        self.assertNotIn(
            "field4", objects_only[3].__dict__, "field4 was not deferred (using only())"
        )
        self.assertNotIn("field1", objects_only[0].get_deferred_fields())

        self.assertIn("field2", objects_only[1].get_deferred_fields())

        # objects_only[2] has several deferred fields, ensure they are all set as such.
        model2c_deferred = objects_only[2].get_deferred_fields()
        self.assertIn("field2", model2c_deferred)
        self.assertIn("field3", model2c_deferred)
        self.assertIn("model2a_ptr_id", model2c_deferred)

        # objects_only[3] has a few more fields that should be set as deferred.
        model2d_deferred = objects_only[3].get_deferred_fields()
        self.assertIn("field2", model2d_deferred)
        self.assertIn("field3", model2d_deferred)
        self.assertIn("field4", model2d_deferred)
        self.assertIn("model2a_ptr_id", model2d_deferred)
        self.assertIn("model2b_ptr_id", model2d_deferred)

        ModelX.objects.create(field_b="A1", field_x="A2")
        ModelY.objects.create(field_b="B1", field_y="B2")

        # If we defer a field on a descendent, the parent's field is not deferred.
        objects_deferred = Base.objects.defer("ModelY___field_y")
        self.assertNotIn("field_y", objects_deferred[0].get_deferred_fields())
        self.assertIn("field_y", objects_deferred[1].get_deferred_fields())

        objects_only = Base.objects.only(
            "polymorphic_ctype", "ModelY___field_y", "ModelX___field_x"
        )
        self.assertIn("field_b", objects_only[0].get_deferred_fields())
        self.assertIn("field_b", objects_only[1].get_deferred_fields())

    def test_defer_related_fields(self):
        self.create_model2abcd()

        objects_deferred_field4 = Model2A.objects.defer("Model2D___field4")
        self.assertNotIn(
            "field4",
            objects_deferred_field4[3].__dict__,
            "field4 was not deferred (using defer(), traversing inheritance)",
        )
        self.assertEqual(objects_deferred_field4[0].__class__, Model2A)
        self.assertEqual(objects_deferred_field4[1].__class__, Model2B)
        self.assertEqual(objects_deferred_field4[2].__class__, Model2C)
        self.assertEqual(objects_deferred_field4[3].__class__, Model2D)

        objects_only_field4 = Model2A.objects.only(
            "polymorphic_ctype",
            "field1",
            "Model2B___id",
            "Model2B___field2",
            "Model2B___model2a_ptr",
            "Model2C___id",
            "Model2C___field3",
            "Model2C___model2b_ptr",
            "Model2D___id",
            "Model2D___model2c_ptr",
        )
        self.assertEqual(objects_only_field4[0].__class__, Model2A)
        self.assertEqual(objects_only_field4[1].__class__, Model2B)
        self.assertEqual(objects_only_field4[2].__class__, Model2C)
        self.assertEqual(objects_only_field4[3].__class__, Model2D)

    def test_manual_get_real_instance(self):
        self.create_model2abcd()

        o = Model2A.objects.non_polymorphic().get(field1="C1")
        self.assertEqual(o.get_real_instance().__class__, Model2C)

    def test_non_polymorphic(self):
        self.create_model2abcd()

        objects = list(Model2A.objects.all().non_polymorphic())
        self.assertQuerysetEqual(
            objects,
            [Model2A, Model2A, Model2A, Model2A],
            transform=lambda o: o.__class__,
        )

    def test_get_real_instances(self):
        self.create_model2abcd()
        qs = Model2A.objects.all().non_polymorphic()

        # from queryset
        objects = qs.get_real_instances()
        self.assertQuerysetEqual(
            objects,
            [Model2A, Model2B, Model2C, Model2D],
            transform=lambda o: o.__class__,
        )

        # from a manual list
        objects = Model2A.objects.get_real_instances(list(qs))
        self.assertQuerysetEqual(
            objects,
            [Model2A, Model2B, Model2C, Model2D],
            transform=lambda o: o.__class__,
        )

        # from empty list
        objects = Model2A.objects.get_real_instances([])
        self.assertQuerysetEqual(objects, [], transform=lambda o: o.__class__)

    def test_queryset_missing_derived(self):
        a = Model2A.objects.create(field1="A1")
        b = Model2B.objects.create(field1="B1", field2="B2")
        c = Model2C.objects.create(field1="C1", field2="C2", field3="C3")
        b_base = Model2A.objects.non_polymorphic().get(pk=b.pk)
        c_base = Model2A.objects.non_polymorphic().get(pk=c.pk)

        b.delete(keep_parents=True)  # e.g. table was truncated

        qs_base = Model2A.objects.order_by("field1").non_polymorphic()
        qs_polymorphic = Model2A.objects.order_by("field1").all()

        self.assertEqual(list(qs_base), [a, b_base, c_base])
        self.assertEqual(list(qs_polymorphic), [a, c])

    def test_queryset_missing_contenttype(self):
        stale_ct = ContentType.objects.create(app_label="tests", model="nonexisting")
        a1 = Model2A.objects.create(field1="A1")
        a2 = Model2A.objects.create(field1="A2")
        c = Model2C.objects.create(field1="C1", field2="C2", field3="C3")
        c_base = Model2A.objects.non_polymorphic().get(pk=c.pk)

        Model2B.objects.filter(pk=a2.pk).update(polymorphic_ctype=stale_ct)

        qs_base = Model2A.objects.order_by("field1").non_polymorphic()
        qs_polymorphic = Model2A.objects.order_by("field1").all()

        self.assertEqual(list(qs_base), [a1, a2, c_base])
        self.assertEqual(list(qs_polymorphic), [a1, a2, c])

    def test_translate_polymorphic_q_object(self):
        self.create_model2abcd()

        q = Model2A.translate_polymorphic_Q_object(Q(instance_of=Model2C))
        objects = Model2A.objects.filter(q)
        self.assertQuerysetEqual(
            objects, [Model2C, Model2D], transform=lambda o: o.__class__, ordered=False
        )

    def test_create_instanceof_q(self):
        q = query_translate.create_instanceof_q([Model2B])
        expected = sorted(
            ContentType.objects.get_for_model(m).pk for m in [Model2B, Model2C, Model2D]
        )
        self.assertEqual(dict(q.children), dict(polymorphic_ctype__in=expected))

    def test_base_manager(self):
        def base_manager(model):
            return (type(model._base_manager), model._base_manager.model)

        self.assertEqual(base_manager(PlainA), (models.Manager, PlainA))
        self.assertEqual(base_manager(PlainB), (models.Manager, PlainB))
        self.assertEqual(base_manager(PlainC), (models.Manager, PlainC))

        self.assertEqual(base_manager(Model2A), (PolymorphicManager, Model2A))
        self.assertEqual(base_manager(Model2B), (PolymorphicManager, Model2B))
        self.assertEqual(base_manager(Model2C), (PolymorphicManager, Model2C))

        self.assertEqual(
            base_manager(One2OneRelatingModel),
            (PolymorphicManager, One2OneRelatingModel),
        )
        self.assertEqual(
            base_manager(One2OneRelatingModelDerived),
            (PolymorphicManager, One2OneRelatingModelDerived),
        )

    def test_instance_default_manager(self):
        def default_manager(instance):
            return (
                type(instance.__class__._default_manager),
                instance.__class__._default_manager.model,
            )

        plain_a = PlainA(field1="C1")
        plain_b = PlainB(field2="C1")
        plain_c = PlainC(field3="C1")

        model_2a = Model2A(field1="C1")
        model_2b = Model2B(field2="C1")
        model_2c = Model2C(field3="C1")

        self.assertEqual(default_manager(plain_a), (models.Manager, PlainA))
        self.assertEqual(default_manager(plain_b), (models.Manager, PlainB))
        self.assertEqual(default_manager(plain_c), (models.Manager, PlainC))

        self.assertEqual(default_manager(model_2a), (PolymorphicManager, Model2A))
        self.assertEqual(default_manager(model_2b), (PolymorphicManager, Model2B))
        self.assertEqual(default_manager(model_2c), (PolymorphicManager, Model2C))

    def test_foreignkey_field(self):
        self.create_model2abcd()

        object2a = Model2A.objects.get(field1="C1")
        self.assertEqual(object2a.model2b.__class__, Model2B)

        object2b = Model2B.objects.get(field1="C1")
        self.assertEqual(object2b.model2c.__class__, Model2C)

    def test_onetoone_field(self):
        self.create_model2abcd()

        # FIXME: We should not use base_objects here.
        a = Model2A.base_objects.get(field1="C1")
        b = One2OneRelatingModelDerived.objects.create(one2one=a, field1="f1", field2="f2")

        # FIXME: this result is basically wrong, probably due to Django cacheing (we used base_objects), but should not be a problem
        self.assertEqual(b.one2one.__class__, Model2A)
        self.assertEqual(b.one2one_id, b.one2one.id)

        c = One2OneRelatingModelDerived.objects.get(field1="f1")
        self.assertEqual(c.one2one.__class__, Model2C)
        self.assertEqual(a.one2onerelatingmodel.__class__, One2OneRelatingModelDerived)

    def test_manytomany_field(self):
        # Model 1
        o = ModelShow1.objects.create(field1="abc")
        o.m2m.add(o)
        o.save()
        self.assertEqual(
            repr(ModelShow1.objects.all()),
            "[ <ModelShow1: id 1, field1 (CharField), m2m (ManyToManyField)> ]",
        )

        # Model 2
        o = ModelShow2.objects.create(field1="abc")
        o.m2m.add(o)
        o.save()
        self.assertEqual(
            repr(ModelShow2.objects.all()),
            '[ <ModelShow2: id 1, field1 "abc", m2m 1> ]',
        )

        # Model 3
        o = ModelShow3.objects.create(field1="abc")
        o.m2m.add(o)
        o.save()
        self.assertEqual(
            repr(ModelShow3.objects.all()),
            '[ <ModelShow3: id 1, field1 (CharField) "abc", m2m (ManyToManyField) 1> ]',
        )
        self.assertEqual(
            repr(ModelShow1.objects.all().annotate(Count("m2m"))),
            "[ <ModelShow1: id 1, field1 (CharField), m2m (ManyToManyField) - Ann: m2m__count (int)> ]",
        )
        self.assertEqual(
            repr(ModelShow2.objects.all().annotate(Count("m2m"))),
            '[ <ModelShow2: id 1, field1 "abc", m2m 1 - Ann: m2m__count 1> ]',
        )
        self.assertEqual(
            repr(ModelShow3.objects.all().annotate(Count("m2m"))),
            '[ <ModelShow3: id 1, field1 (CharField) "abc", m2m (ManyToManyField) 1 - Ann: m2m__count (int) 1> ]',
        )

        # no pretty printing
        ModelShow1_plain.objects.create(field1="abc")
        ModelShow2_plain.objects.create(field1="abc", field2="def")
        self.assertQuerysetEqual(
            ModelShow1_plain.objects.all(),
            [ModelShow1_plain, ModelShow2_plain],
            transform=lambda o: o.__class__,
            ordered=False,
        )

    def test_extra_method(self):
        a, b, c, d = self.create_model2abcd()

        objects = Model2A.objects.extra(where=[f"id IN ({b.id}, {c.id})"])
        self.assertQuerysetEqual(
            objects, [Model2B, Model2C], transform=lambda o: o.__class__, ordered=False
        )

        objects = Model2A.objects.extra(
            select={"select_test": "field1 = 'A1'"},
            where=["field1 = 'A1' OR field1 = 'B1'"],
            order_by=["-id"],
        )
        self.assertQuerysetEqual(objects, [Model2B, Model2A], transform=lambda o: o.__class__)

        ModelExtraA.objects.create(field1="A1")
        ModelExtraB.objects.create(field1="B1", field2="B2")
        ModelExtraC.objects.create(field1="C1", field2="C2", field3="C3")
        ModelExtraExternal.objects.create(topic="extra1")
        ModelExtraExternal.objects.create(topic="extra2")
        ModelExtraExternal.objects.create(topic="extra3")
        objects = ModelExtraA.objects.extra(
            tables=["tests_modelextraexternal"],
            select={"topic": "tests_modelextraexternal.topic"},
            where=["tests_modelextraa.id = tests_modelextraexternal.id"],
        )
        self.assertEqual(
            repr(objects[0]),
            '<ModelExtraA: id 1, field1 (CharField) "A1" - Extra: topic (str) "extra1">',
        )
        self.assertEqual(
            repr(objects[1]),
            '<ModelExtraB: id 2, field1 (CharField) "B1", field2 (CharField) "B2" - Extra: topic (str) "extra2">',
        )
        self.assertEqual(
            repr(objects[2]),
            '<ModelExtraC: id 3, field1 (CharField) "C1", field2 (CharField) "C2", field3 (CharField) "C3" - Extra: topic (str) "extra3">',
        )
        self.assertEqual(len(objects), 3)

    def test_instance_of_filter(self):
        self.create_model2abcd()

        objects = Model2A.objects.instance_of(Model2B)
        self.assertQuerysetEqual(
            objects,
            [Model2B, Model2C, Model2D],
            transform=lambda o: o.__class__,
            ordered=False,
        )

        objects = Model2A.objects.filter(instance_of=Model2B)
        self.assertQuerysetEqual(
            objects,
            [Model2B, Model2C, Model2D],
            transform=lambda o: o.__class__,
            ordered=False,
        )

        objects = Model2A.objects.filter(Q(instance_of=Model2B))
        self.assertQuerysetEqual(
            objects,
            [Model2B, Model2C, Model2D],
            transform=lambda o: o.__class__,
            ordered=False,
        )

        objects = Model2A.objects.not_instance_of(Model2B)
        self.assertQuerysetEqual(
            objects, [Model2A], transform=lambda o: o.__class__, ordered=False
        )

    def test_polymorphic___filter(self):
        self.create_model2abcd()

        objects = Model2A.objects.filter(Q(Model2B___field2="B2") | Q(Model2C___field3="C3"))
        self.assertQuerysetEqual(
            objects, [Model2B, Model2C], transform=lambda o: o.__class__, ordered=False
        )

    def test_polymorphic_applabel___filter(self):
        self.create_model2abcd()

        assert Model2B._meta.app_label == "tests"
        objects = Model2A.objects.filter(
            Q(tests__Model2B___field2="B2") | Q(tests__Model2C___field3="C3")
        )
        self.assertQuerysetEqual(
            objects, [Model2B, Model2C], transform=lambda o: o.__class__, ordered=False
        )

    def test_query_filter_exclude_is_immutable(self):
        # given
        q_to_reuse = Q(Model2B___field2="something")
        untouched_q_object = Q(Model2B___field2="something")
        # when
        Model2A.objects.filter(q_to_reuse).all()
        # then
        self.assertEqual(q_to_reuse.children, untouched_q_object.children)

        # given
        q_to_reuse = Q(Model2B___field2="something")
        untouched_q_object = Q(Model2B___field2="something")
        # when
        Model2B.objects.filter(q_to_reuse).all()
        # then
        self.assertEqual(q_to_reuse.children, untouched_q_object.children)

    def test_polymorphic___filter_field(self):
        p = ModelUnderRelParent.objects.create(_private=True, field1="AA")
        ModelUnderRelChild.objects.create(parent=p, _private2=True)

        # The "___" filter should also parse to "parent" -> "_private" as fallback.
        objects = ModelUnderRelChild.objects.filter(parent___private=True)
        self.assertEqual(len(objects), 1)

    def test_polymorphic___filter_reverse_field(self):
        p = ModelUnderRelParent.objects.create(_private=True, field1="BB")
        ModelUnderRelChild.objects.create(parent=p, _private2=True)

        # Also test for reverse relations
        objects = ModelUnderRelParent.objects.filter(children___private2=True)
        self.assertEqual(len(objects), 1)

    def test_delete(self):
        a, b, c, d = self.create_model2abcd()

        oa = Model2A.objects.get(id=b.id)
        self.assertEqual(oa.__class__, Model2B)
        self.assertEqual(Model2A.objects.count(), 4)

        oa.delete()
        objects = Model2A.objects.all()
        self.assertQuerysetEqual(
            objects,
            [Model2A, Model2C, Model2D],
            transform=lambda o: o.__class__,
            ordered=False,
        )

    def test_combine_querysets(self):
        ModelX.objects.create(field_x="x", field_b="1")
        ModelY.objects.create(field_y="y", field_b="2")

        qs = Base.objects.instance_of(ModelX) | Base.objects.instance_of(ModelY)
        qs = qs.order_by("field_b")
        self.assertEqual(repr(qs[0]), "<ModelX: id 1, field_b (CharField), field_x (CharField)>")
        self.assertEqual(repr(qs[1]), "<ModelY: id 2, field_b (CharField), field_y (CharField)>")
        self.assertEqual(len(qs), 2)

    def test_multiple_inheritance(self):
        # multiple inheritance, subclassing third party models (mix PolymorphicModel with models.Model)

        Enhance_Base.objects.create(field_b="b-base")
        Enhance_Inherit.objects.create(field_b="b-inherit", field_p="p", field_i="i")

        qs = Enhance_Base.objects.all()
        self.assertEqual(len(qs), 2)
        self.assertEqual(
            repr(qs[0]),
            '<Enhance_Base: base_id (AutoField/pk) 1, field_b (CharField) "b-base">',
        )
        self.assertEqual(
            repr(qs[1]),
            '<Enhance_Inherit: base_id (AutoField/pk) 2, field_b (CharField) "b-inherit", id 1, field_p (CharField) "p", field_i (CharField) "i">',
        )

    def test_relation_base(self):
        # ForeignKey, ManyToManyField
        obase = RelationBase.objects.create(field_base="base")
        oa = RelationA.objects.create(field_base="A1", field_a="A2", fk=obase)
        ob = RelationB.objects.create(field_base="B1", field_b="B2", fk=oa)
        oc = RelationBC.objects.create(field_base="C1", field_b="C2", field_c="C3", fk=oa)
        oa.m2m.add(oa)
        oa.m2m.add(ob)

        objects = RelationBase.objects.all()
        self.assertEqual(
            repr(objects[0]),
            f'<RelationBase: id {objects[0].pk}, field_base (CharField) "base", fk (ForeignKey) None, m2m (ManyToManyField) 0>',
        )
        self.assertEqual(
            repr(objects[1]),
            f'<RelationA: id {objects[1].pk}, field_base (CharField) "A1", fk (ForeignKey) RelationBase, field_a (CharField) "A2", m2m (ManyToManyField) 2>',
        )
        self.assertEqual(
            repr(objects[2]),
            f'<RelationB: id {objects[2].pk}, field_base (CharField) "B1", fk (ForeignKey) RelationA, field_b (CharField) "B2", m2m (ManyToManyField) 1>',
        )
        self.assertEqual(
            repr(objects[3]),
            f'<RelationBC: id {objects[3].pk}, field_base (CharField) "C1", fk (ForeignKey) RelationA, field_b (CharField) "C2", field_c (CharField) "C3", m2m (ManyToManyField) 0>',
        )
        self.assertEqual(len(objects), 4)

        boa = RelationBase.objects.get(id=oa.pk)
        self.assertEqual(
            repr(boa.fk),
            f'<RelationBase: id {boa.fk.pk}, field_base (CharField) "base", fk (ForeignKey) None, m2m (ManyToManyField) 0>',
        )

        objects = boa.relationbase_set.all()
        self.assertEqual(
            repr(objects[0]),
            f'<RelationB: id {objects[0].pk}, field_base (CharField) "B1", fk (ForeignKey) RelationA, field_b (CharField) "B2", m2m (ManyToManyField) 1>',
        )
        self.assertEqual(
            repr(objects[1]),
            f'<RelationBC: id {objects[1].pk}, field_base (CharField) "C1", fk (ForeignKey) RelationA, field_b (CharField) "C2", field_c (CharField) "C3", m2m (ManyToManyField) 0>',
        )
        self.assertEqual(len(objects), 2)

        bob = RelationBase.objects.get(id=ob.pk)
        self.assertEqual(
            repr(bob.fk),
            f'<RelationA: id {bob.fk.pk}, field_base (CharField) "A1", fk (ForeignKey) RelationBase, field_a (CharField) "A2", m2m (ManyToManyField) 2>',
        )

        aoa = RelationA.objects.get()
        objects = aoa.m2m.all()
        self.assertEqual(
            repr(objects[0]),
            f'<RelationA: id {objects[0].pk}, field_base (CharField) "A1", fk (ForeignKey) RelationBase, field_a (CharField) "A2", m2m (ManyToManyField) 2>',
        )
        self.assertEqual(
            repr(objects[1]),
            f'<RelationB: id {objects[1].pk}, field_base (CharField) "B1", fk (ForeignKey) RelationA, field_b (CharField) "B2", m2m (ManyToManyField) 1>',
        )
        self.assertEqual(len(objects), 2)

    def test_user_defined_manager(self):
        self.create_model2abcd()
        ModelWithMyManager.objects.create(field1="D1a", field4="D4a")
        ModelWithMyManager.objects.create(field1="D1b", field4="D4b")

        # MyManager should reverse the sorting of field1
        objects = ModelWithMyManager.objects.all()
        self.assertQuerysetEqual(
            objects,
            [(ModelWithMyManager, "D1b", "D4b"), (ModelWithMyManager, "D1a", "D4a")],
            transform=lambda o: (o.__class__, o.field1, o.field4),
        )

        self.assertIs(type(ModelWithMyManager.objects), MyManager)
        self.assertIs(type(ModelWithMyManager._default_manager), MyManager)

    def test_user_defined_manager_as_secondary(self):
        self.create_model2abcd()
        ModelWithMyManagerNoDefault.objects.create(field1="D1a", field4="D4a")
        ModelWithMyManagerNoDefault.objects.create(field1="D1b", field4="D4b")

        # MyManager should reverse the sorting of field1
        objects = ModelWithMyManagerNoDefault.my_objects.all()
        self.assertQuerysetEqual(
            objects,
            [
                (ModelWithMyManagerNoDefault, "D1b", "D4b"),
                (ModelWithMyManagerNoDefault, "D1a", "D4a"),
            ],
            transform=lambda o: (o.__class__, o.field1, o.field4),
        )

        self.assertIs(type(ModelWithMyManagerNoDefault.my_objects), MyManager)
        self.assertIs(type(ModelWithMyManagerNoDefault.objects), PolymorphicManager)
        self.assertIs(type(ModelWithMyManagerNoDefault._default_manager), PolymorphicManager)

    def test_user_objects_manager_as_secondary(self):
        self.create_model2abcd()
        ModelWithMyManagerDefault.objects.create(field1="D1a", field4="D4a")
        ModelWithMyManagerDefault.objects.create(field1="D1b", field4="D4b")

        self.assertIs(type(ModelWithMyManagerDefault.my_objects), MyManager)
        self.assertIs(type(ModelWithMyManagerDefault.objects), PolymorphicManager)
        self.assertIs(type(ModelWithMyManagerDefault._default_manager), MyManager)

    def test_user_defined_queryset_as_manager(self):
        self.create_model2abcd()
        ModelWithMyManager2.objects.create(field1="D1a", field4="D4a")
        ModelWithMyManager2.objects.create(field1="D1b", field4="D4b")

        objects = ModelWithMyManager2.objects.all()
        self.assertQuerysetEqual(
            objects,
            [(ModelWithMyManager2, "D1a", "D4a"), (ModelWithMyManager2, "D1b", "D4b")],
            transform=lambda o: (o.__class__, o.field1, o.field4),
            ordered=False,
        )

        self.assertEqual(
            type(ModelWithMyManager2.objects).__name__,
            "PolymorphicManagerFromMyManagerQuerySet",
        )
        self.assertEqual(
            type(ModelWithMyManager2._default_manager).__name__,
            "PolymorphicManagerFromMyManagerQuerySet",
        )

    def test_manager_inheritance(self):
        # by choice of MRO, should be MyManager from MROBase1.
        self.assertIs(type(MRODerived.objects), MyManager)

    def test_queryset_assignment(self):
        # This is just a consistency check for now, testing standard Django behavior.
        parent = PlainParentModelWithManager.objects.create()
        child = PlainChildModelWithManager.objects.create(fk=parent)
        self.assertIs(type(PlainParentModelWithManager._default_manager), models.Manager)
        self.assertIs(type(PlainChildModelWithManager._default_manager), PlainMyManager)
        self.assertIs(type(PlainChildModelWithManager.objects), PlainMyManager)
        self.assertIs(type(PlainChildModelWithManager.objects.all()), PlainMyManagerQuerySet)

        # A related set is created using the model's _default_manager, so does gain extra methods.
        self.assertIs(type(parent.childmodel_set.my_queryset_foo()), PlainMyManagerQuerySet)

        # For polymorphic models, the same should happen.
        parent = ParentModelWithManager.objects.create()
        child = ChildModelWithManager.objects.create(fk=parent)
        self.assertIs(type(ParentModelWithManager._default_manager), PolymorphicManager)
        self.assertIs(type(ChildModelWithManager._default_manager), MyManager)
        self.assertIs(type(ChildModelWithManager.objects), MyManager)
        self.assertIs(type(ChildModelWithManager.objects.my_queryset_foo()), MyManagerQuerySet)

        # A related set is created using the model's _default_manager, so does gain extra methods.
        self.assertIs(type(parent.childmodel_set.my_queryset_foo()), MyManagerQuerySet)

    def test_proxy_models(self):
        # prepare some data
        for data in ("bleep bloop", "I am a", "computer"):
            ProxyChild.objects.create(some_data=data)

        # this caches ContentType queries so they don't interfere with our query counts later
        list(ProxyBase.objects.all())

        # one query per concrete class
        with self.assertNumQueries(1):
            items = list(ProxyBase.objects.all())

        self.assertIsInstance(items[0], ProxyChild)

    def test_queryset_on_proxy_model_does_not_return_superclasses(self):
        ProxyBase.objects.create(some_data="Base1")
        ProxyBase.objects.create(some_data="Base2")
        ProxyChild.objects.create(some_data="Child1")
        ProxyChild.objects.create(some_data="Child2")
        ProxyChild.objects.create(some_data="Child3")

        self.assertEqual(5, ProxyBase.objects.count())
        self.assertEqual(3, ProxyChild.objects.count())

    def test_queryset_on_polymorphic_proxy_model_returns_superclasses(self):
        ProxyBase.objects.create(some_data="Base1")
        AliasProxyChild.objects.create(some_data="ProxyChild1")
        AliasProxyChild.objects.create(some_data="ProxyChild2")
        ProxyChild.objects.create(some_data="PolyChild1")
        NonAliasNonProxyChild.objects.create(some_data="SubChild1")
        NonAliasNonProxyChild.objects.create(some_data="SubChild2")
        NonProxyChild.objects.create(some_data="NonProxChild1", name="t1")

        with self.subTest(" superclasses"):
            self.assertEqual(7, ProxyBase.objects.count())
            self.assertEqual(7, AliasProxyChild.objects.count())
        with self.subTest("only compete classes"):
            # Non proxy models should not return the proxy siblings
            self.assertEqual(1, ProxyChild.objects.count())
            self.assertEqual(2, NonAliasNonProxyChild.objects.count())
            self.assertEqual(3, NonProxyChild.objects.count())

    def test_polymorphic_proxy_object_has_different_ctype_from_base(self):
        obj1 = ProxyBase.objects.create(some_data="Base1")
        obj2 = AliasProxyChild.objects.create(some_data="ProxyChild1")
        obj1_ctype = ContentType.objects.get_for_model(obj1, for_concrete_model=False)
        obj2_ctype = ContentType.objects.get_for_model(obj2, for_concrete_model=False)
        self.assertNotEqual(obj1_ctype, obj2_ctype)

    def test_can_create_django_style_proxy_classes_alias(self):
        ProxyBase.objects.create(some_data="Base1")
        TradProxyChild.objects.create(some_data="Base2")
        self.assertEqual(2, ProxyBase.objects.count())
        self.assertEqual(2, TradProxyChild.objects.count())
        TradProxyOnProxyChild.objects.create()

    def test_convert_back_to_django_style_from_polymorphic(self):
        ProxyBase.objects.create(some_data="Base1")
        ProxyChild.objects.create(some_data="Base1")
        TradProxyOnProxyChild.objects.create(some_data="Base3")

        self.assertEqual(3, ProxyBase.objects.count())
        self.assertEqual(2, ProxyChild.objects.count())
        self.assertEqual(3, TradProxyOnProxyChild.objects.count())

    def test_convert_back_to_django_style_from_polymorphic_stops_at_concrete(self):
        ProxyBase.objects.create(some_data="Base1")
        NonProxyChild.objects.create(some_data="Base1")
        AliasOfNonProxyChild.objects.create(some_data="Base1")

        self.assertEqual(3, ProxyBase.objects.count())
        self.assertEqual(2, NonProxyChild.objects.count())
        self.assertEqual(2, AliasOfNonProxyChild.objects.count())

    def test_revert_back_to_polymorphic_proxy(self):
        self.assertFalse(ProxyChildAliasProxy._meta.polymorphic__proxy)

    def test_proxy_get_real_instance_class(self):
        """
        The call to ``get_real_instance()`` also checks whether the returned model is of the correct type.
        This unit test guards that this check is working properly. For instance,
        proxy child models need to be handled separately.
        """
        name = "Item1"
        nonproxychild = NonProxyChild.objects.create(name=name)

        pb = ProxyBase.objects.get(id=nonproxychild.pk)
        self.assertEqual(pb.get_real_instance_class(), NonProxyChild)
        self.assertEqual(pb.get_real_instance(), nonproxychild)
        self.assertEqual(pb.name, name)

        pbm = NonProxyChild.objects.get(id=nonproxychild.pk)
        self.assertEqual(pbm.get_real_instance_class(), NonProxyChild)
        self.assertEqual(pbm.get_real_instance(), nonproxychild)
        self.assertEqual(pbm.name, name)

    def test_content_types_for_proxy_models(self):
        """Checks if ContentType is capable of returning proxy models."""
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(ProxyChild, for_concrete_model=False)
        self.assertEqual(ProxyChild, ct.model_class())

    def test_proxy_model_inheritance(self):
        """
        Polymorphic abilities should also work when the base model is a proxy object.
        """
        # The managers should point to the proper objects.
        # otherwise, the whole excersise is pointless.
        self.assertEqual(ProxiedBase.objects.model, ProxiedBase)
        self.assertEqual(ProxyModelBase.objects.model, ProxyModelBase)
        self.assertEqual(ProxyModelA.objects.model, ProxyModelA)
        self.assertEqual(ProxyModelB.objects.model, ProxyModelB)

        # Create objects
        object1_pk = ProxyModelA.objects.create(name="object1").pk
        object2_pk = ProxyModelB.objects.create(name="object2", field2="bb").pk

        # Getting single objects
        object1 = ProxyModelBase.objects.get(name="object1")
        object2 = ProxyModelBase.objects.get(name="object2")
        self.assertEqual(
            repr(object1),
            '<ProxyModelA: id %i, name (CharField) "object1", field1 (CharField) "">' % object1_pk,
        )
        self.assertEqual(
            repr(object2),
            '<ProxyModelB: id %i, name (CharField) "object2", field2 (CharField) "bb">'
            % object2_pk,
        )
        self.assertIsInstance(object1, ProxyModelA)
        self.assertIsInstance(object2, ProxyModelB)

        # Same for lists
        objects = list(ProxyModelBase.objects.all().order_by("name"))
        self.assertEqual(
            repr(objects[0]),
            '<ProxyModelA: id %i, name (CharField) "object1", field1 (CharField) "">' % object1_pk,
        )
        self.assertEqual(
            repr(objects[1]),
            '<ProxyModelB: id %i, name (CharField) "object2", field2 (CharField) "bb">'
            % object2_pk,
        )
        self.assertIsInstance(objects[0], ProxyModelA)
        self.assertIsInstance(objects[1], ProxyModelB)

    def test_custom_pk(self):
        CustomPkBase.objects.create(b="b")
        CustomPkInherit.objects.create(b="b", i="i")
        qs = CustomPkBase.objects.all()
        self.assertEqual(len(qs), 2)
        self.assertEqual(repr(qs[0]), '<CustomPkBase: id 1, b (CharField) "b">')
        self.assertEqual(
            repr(qs[1]),
            '<CustomPkInherit: id 2, b (CharField) "b", custom_id (AutoField/pk) 1, i (CharField) "i">',
        )

    def test_fix_getattribute(self):
        # fixed issue in PolymorphicModel.__getattribute__: field name same as model name
        o = ModelFieldNameTest.objects.create(modelfieldnametest="1")
        self.assertEqual(repr(o), "<ModelFieldNameTest: id 1, modelfieldnametest (CharField)>")

        # if subclass defined __init__ and accessed class members,
        # __getattribute__ had a problem: "...has no attribute 'sub_and_superclass_dict'"
        o = InitTestModelSubclass.objects.create()
        self.assertEqual(o.bar, "XYZ")

    def test_parent_link_and_related_name(self):
        t = TestParentLinkAndRelatedName(field1="TestParentLinkAndRelatedName")
        t.save()
        p = ModelShow1_plain.objects.get(field1="TestParentLinkAndRelatedName")

        # check that p is equal to the
        self.assertIsInstance(p, TestParentLinkAndRelatedName)
        self.assertEqual(p, t)

        # check that the accessors to parent and sublass work correctly and return the right object
        p = ModelShow1_plain.objects.non_polymorphic().get(field1="TestParentLinkAndRelatedName")
        # p should be Plain1 and t TestParentLinkAndRelatedName, so not equal
        self.assertNotEqual(p, t)
        self.assertEqual(p, t.superclass)
        self.assertEqual(p.related_name_subclass, t)

        # test that we can delete the object
        t.delete()

    def test_polymorphic__accessor_caching(self):
        blog_a = BlogA.objects.create(name="blog")

        blog_base = BlogBase.objects.non_polymorphic().get(id=blog_a.id)
        blog_a = BlogA.objects.get(id=blog_a.id)

        # test reverse accessor & check that we get back cached object on repeated access
        self.assertEqual(blog_base.bloga, blog_a)
        self.assertIs(blog_base.bloga, blog_base.bloga)
        cached_blog_a = blog_base.bloga

        # test forward accessor & check that we get back cached object on repeated access
        self.assertEqual(blog_a.blogbase_ptr, blog_base)
        self.assertIs(blog_a.blogbase_ptr, blog_a.blogbase_ptr)
        cached_blog_base = blog_a.blogbase_ptr

        # check that refresh_from_db correctly clears cached related objects
        blog_base.refresh_from_db()
        blog_a.refresh_from_db()

        self.assertIsNot(cached_blog_a, blog_base.bloga)
        self.assertIsNot(cached_blog_base, blog_a.blogbase_ptr)

    def test_polymorphic__aggregate(self):
        """test ModelX___field syntax on aggregate (should work for annotate either)"""

        Model2A.objects.create(field1="A1")
        Model2B.objects.create(field1="A1", field2="B2")
        Model2B.objects.create(field1="A1", field2="B2")

        # aggregate using **kwargs
        result = Model2A.objects.aggregate(cnt=Count("Model2B___field2"))
        self.assertEqual(result, {"cnt": 2})

        # aggregate using **args
        self.assertRaisesMessage(
            AssertionError,
            "PolymorphicModel: annotate()/aggregate(): ___ model lookup supported for keyword arguments only",
            lambda: Model2A.objects.aggregate(Count("Model2B___field2")),
        )

    def test_polymorphic__complex_aggregate(self):
        """test (complex expression on) aggregate (should work for annotate either)"""

        Model2A.objects.create(field1="A1")
        Model2B.objects.create(field1="A1", field2="B2")
        Model2B.objects.create(field1="A1", field2="B2")

        # aggregate using **kwargs
        result = Model2A.objects.aggregate(
            cnt_a1=Count(Case(When(field1="A1", then=1))),
            cnt_b2=Count(Case(When(Model2B___field2="B2", then=1))),
        )
        self.assertEqual(result, {"cnt_b2": 2, "cnt_a1": 3})

        # aggregate using **args
        # we have to set the defaul alias or django won't except a complex expression
        # on aggregate/annotate
        def ComplexAgg(expression):
            complexagg = Count(expression) * 10
            complexagg.default_alias = "complexagg"
            return complexagg

        with self.assertRaisesMessage(
            AssertionError,
            "PolymorphicModel: annotate()/aggregate(): ___ model lookup supported for keyword arguments only",
        ):
            Model2A.objects.aggregate(ComplexAgg("Model2B___field2"))

    def test_polymorphic__filtered_relation(self):
        """test annotation using FilteredRelation"""

        blog = BlogA.objects.create(name="Ba1", info="i1 joined")
        blog.blogentry_set.create(text="bla1 joined")
        blog.blogentry_set.create(text="bla2 joined")
        blog.blogentry_set.create(text="bla3 joined")
        blog.blogentry_set.create(text="bla4")
        blog.blogentry_set.create(text="bla5")
        BlogA.objects.create(name="Ba2", info="i2 joined")
        BlogA.objects.create(name="Ba3", info="i3")
        BlogB.objects.create(name="Bb3")

        result = BlogA.objects.annotate(
            text_joined=FilteredRelation(
                "blogentry", condition=Q(blogentry__text__contains="joined")
            ),
        ).aggregate(Count("text_joined"))
        self.assertEqual(result, {"text_joined__count": 3})

        result = BlogA.objects.annotate(
            text_joined=FilteredRelation(
                "blogentry", condition=Q(blogentry__text__contains="joined")
            ),
        ).aggregate(count=Count("text_joined"))
        self.assertEqual(result, {"count": 3})

        result = BlogBase.objects.annotate(
            info_joined=FilteredRelation("bloga", condition=Q(BlogA___info__contains="joined")),
        ).aggregate(Count("info_joined"))
        self.assertEqual(result, {"info_joined__count": 2})

        result = BlogBase.objects.annotate(
            info_joined=FilteredRelation("bloga", condition=Q(BlogA___info__contains="joined")),
        ).aggregate(count=Count("info_joined"))
        self.assertEqual(result, {"count": 2})

        # We should get a BlogA and a BlogB
        result = BlogBase.objects.annotate(
            info_joined=FilteredRelation("bloga", condition=Q(BlogA___info__contains="joined")),
        ).filter(info_joined__isnull=True)
        self.assertEqual(result.count(), 2)
        self.assertIsInstance(result.first(), BlogA)
        self.assertIsInstance(result.last(), BlogB)

    def test_polymorphic__expressions(self):
        from django.db.models.functions import Concat

        # no exception raised
        result = Model2B.objects.annotate(val=Concat("field1", "field2"))
        self.assertEqual(list(result), [])

    def test_null_polymorphic_id(self):
        """Test that a proper error message is displayed when the database lacks the ``polymorphic_ctype_id``"""
        Model2A.objects.create(field1="A1")
        Model2B.objects.create(field1="A1", field2="B2")
        Model2B.objects.create(field1="A1", field2="B2")
        Model2A.objects.all().update(polymorphic_ctype_id=None)

        with self.assertRaises(PolymorphicTypeUndefined):
            list(Model2A.objects.all())

    def test_invalid_polymorphic_id(self):
        """Test that a proper error message is displayed when the database ``polymorphic_ctype_id`` is invalid"""
        Model2A.objects.create(field1="A1")
        Model2B.objects.create(field1="A1", field2="B2")
        Model2B.objects.create(field1="A1", field2="B2")
        invalid = ContentType.objects.get_for_model(PlainA).pk
        Model2A.objects.all().update(polymorphic_ctype_id=invalid)

        with self.assertRaises(PolymorphicTypeInvalid):
            list(Model2A.objects.all())

    def test_bulk_create_abstract_inheritance(self):
        ArtProject.objects.bulk_create(
            [
                ArtProject(topic="Painting with Tim", artist="T. Turner"),
                ArtProject(topic="Sculpture with Tim", artist="T. Turner"),
            ]
        )
        self.assertEqual(
            sorted(ArtProject.objects.values_list("topic", "artist")),
            [("Painting with Tim", "T. Turner"), ("Sculpture with Tim", "T. Turner")],
        )

    def test_bulk_create_proxy_inheritance(self):
        RedheadDuck.objects.bulk_create(
            [
                RedheadDuck(name="redheadduck1"),
                Duck(name="duck1"),
                RubberDuck(name="rubberduck1"),
            ]
        )
        RubberDuck.objects.bulk_create(
            [
                RedheadDuck(name="redheadduck2"),
                RubberDuck(name="rubberduck2"),
                Duck(name="duck2"),
            ]
        )
        self.assertEqual(
            sorted(RedheadDuck.objects.values_list("name", flat=True)),
            ["redheadduck1", "redheadduck2"],
        )
        self.assertEqual(
            sorted(RubberDuck.objects.values_list("name", flat=True)),
            ["rubberduck1", "rubberduck2"],
        )
        self.assertEqual(
            sorted(Duck.objects.values_list("name", flat=True)),
            [
                "duck1",
                "duck2",
                "redheadduck1",
                "redheadduck2",
                "rubberduck1",
                "rubberduck2",
            ],
        )

    def test_bulk_create_unsupported_multi_table_inheritance(self):
        with self.assertRaises(ValueError):
            MultiTableDerived.objects.bulk_create(
                [MultiTableDerived(field1="field1", field2="field2")]
            )

    def test_bulk_create_ignore_conflicts(self):
        ArtProject.objects.bulk_create(
            [
                ArtProject(topic="Painting with Tim", artist="T. Turner"),
                ArtProject.objects.create(topic="Sculpture with Tim", artist="T. Turner"),
            ],
            ignore_conflicts=True,
        )
        self.assertEqual(ArtProject.objects.count(), 2)

    def test_bulk_create_no_ignore_conflicts(self):
        with self.assertRaises(IntegrityError):
            ArtProject.objects.bulk_create(
                [
                    ArtProject(topic="Painting with Tim", artist="T. Turner"),
                    ArtProject.objects.create(topic="Sculpture with Tim", artist="T. Turner"),
                ],
                ignore_conflicts=False,
            )
        self.assertEqual(ArtProject.objects.count(), 1)

    def test_can_query_using_subclass_selector_on_abstract_model(self):
        obj = SubclassSelectorAbstractConcreteModel.objects.create(concrete_field="abc")

        queried_obj = SubclassSelectorAbstractBaseModel.objects.filter(
            SubclassSelectorAbstractConcreteModel___concrete_field="abc"
        ).get()

        self.assertEqual(obj.pk, queried_obj.pk)

    def test_can_query_using_subclass_selector_on_proxy_model(self):
        obj = SubclassSelectorProxyConcreteModel.objects.create(concrete_field="abc")

        queried_obj = SubclassSelectorProxyBaseModel.objects.filter(
            SubclassSelectorProxyConcreteModel___concrete_field="abc"
        ).get()

        self.assertEqual(obj.pk, queried_obj.pk)

    def test_prefetch_related_behaves_normally_with_polymorphic_model(self):
        b1 = RelatingModel.objects.create()
        b2 = RelatingModel.objects.create()
        a = b1.many2many.create()  # create Model2A
        b2.many2many.add(a)  # add same to second relating model
        qs = RelatingModel.objects.prefetch_related("many2many")
        for obj in qs:
            self.assertEqual(len(obj.many2many.all()), 1)

    def test_prefetch_related_with_missing(self):
        b1 = RelatingModel.objects.create()
        b2 = RelatingModel.objects.create()

        rel1 = Model2A.objects.create(field1="A1")
        rel2 = Model2B.objects.create(field1="A2", field2="B2")

        b1.many2many.add(rel1)
        b2.many2many.add(rel2)

        rel2.delete(keep_parents=True)

        qs = RelatingModel.objects.order_by("pk").prefetch_related("many2many")
        objects = list(qs)
        self.assertEqual(len(objects[0].many2many.all()), 1)

        # derived object was not fetched
        self.assertEqual(len(objects[1].many2many.all()), 0)

        # base object does exist
        self.assertEqual(len(objects[1].many2many.non_polymorphic()), 1)

    def test_refresh_from_db_fields(self):
        """Test whether refresh_from_db(fields=..) works as it performs .only() queries"""
        obj = Model2B.objects.create(field1="aa", field2="bb")
        Model2B.objects.filter(pk=obj.pk).update(field1="aa1", field2="bb2")
        obj.refresh_from_db(fields=["field2"])
        assert obj.field1 == "aa"
        assert obj.field2 == "bb2"

        obj.refresh_from_db(fields=["field1"])
        assert obj.field1 == "aa1"

    def test_non_polymorphic_parent(self):
        obj = NonPolymorphicParent.objects.create()
        assert obj.delete()

    def test_normal_django_to_poly_related_give_poly_type(self):
        obj1 = ParentModel.objects.create(name="m1")
        obj2 = ChildModel.objects.create(name="m2", other_name="m2")
        obj3 = ChildModel.objects.create(name="m1")

        PlainModel.objects.create(relation=obj1)
        PlainModel.objects.create(relation=obj2)
        PlainModel.objects.create(relation=obj3)

        ct = ContentType.objects.get_for_model(AltChildModel, for_concrete_model=True)

        with self.assertNumQueries(6):
            # Queries will be
            #    * 1 for All PlainModels object (1)
            #    * 1 for each relations ParentModel (4)
            #    * 1 for each relations ChilModel is needed (3)
            multi_q = [
                # these obj.relation values will have their proper sub type
                obj.relation
                for obj in PlainModel.objects.all()
            ]
            multi_q_types = [type(obj) for obj in multi_q]

        with self.assertNumQueries(2):
            grouped_q = [
                # these obj.relation values will all be ParentModel's
                # unless we fix select related but should be their proper
                # sub type by using PolymorphicRelatedQuerySetMixin
                obj.relation
                for obj in PlainModel.objects.select_related("relation")
            ]
            grouped_q_types = [type(obj) for obj in grouped_q]

        self.assertListEqual(multi_q_types, grouped_q_types)
        self.assertListEqual(grouped_q, [obj1, obj2, obj3])

    def test_normal_django_to_poly_related_give_poly_type_using_select_related_true(self):
        obj1 = ParentModel.objects.create(name="m1")
        obj2 = ChildModel.objects.create(name="m2", other_name="m2")
        obj3 = ChildModel.objects.create(name="m1")
        obj4 = AltChildAsBaseModel.objects.create(
            name="ac2", other_name="ac2name", more_name="ac2morename"
        )

        PlainModel.objects.create(relation=obj1)
        PlainModel.objects.create(relation=obj2)
        PlainModel.objects.create(relation=obj3)
        PlainModel.objects.create(relation=obj4)

        with self.assertNumQueries(8):
            # Queries will be
            #    * 1 for All PlainModels object (x1)
            #    * 1 for each relations ParentModel (x4)
            #    * 1 for each relations ChildModel is needed (x2)
            #    * 1 for each relations AltChildAsBaseModel is needed (x1)
            multi_q = [
                # these obj.relation values will have their proper sub type
                obj.relation
                for obj in PlainModel.objects.all()
            ]
            multi_q_types = [type(obj) for obj in multi_q]

        with self.assertNumQueries(3):
            grouped_q = [
                # these obj.relation values will all be ParentModel's
                # unless we fix select related but should be their proper
                # sub type by using PolymorphicRelatedQuerySetMixin
                # ATM: we require 1 query fro each type. Although this can
                # be reduced by specifying the relations to the polymorphic
                # classes. BUT this has the downside of making the query have
                # a large number of joins
                obj.relation
                for obj in PlainModel.objects.select_related()
            ]
            grouped_q_types = [type(obj) for obj in grouped_q]

        self.assertListEqual(multi_q_types, grouped_q_types)
        self.assertListEqual(grouped_q, [obj1, obj2, obj3, obj4])

    def test_prefetch_base_load_359(self):
        obj1_1 = ModelShow1_plain.objects.create(field1="1")
        obj2_1 = ModelShow2_plain.objects.create(field1="2", field2="1")
        obj3_2 = ModelShow2_plain.objects.create(field1="3", field2="2")

        with self.assertNumQueries(1):
            obj = ModelShow2_plain.objects.filter(pk=obj2_1.pk)[0]
            _ = (obj.field1, obj.field1)

    def test_select_related_on_poly_classes(self):
        plain_a_obj_1 = PlainA.objects.create(field1="f1")
        plain_a_obj_2 = PlainA.objects.create(field1="f2")
        extra_obj = ModelExtraExternal.objects.create(topic="t1")
        obj_p = ParentModel.objects.create(name="p1")
        obj_c = ChildModel.objects.create(name="c1", other_name="c1name", link_on_child=extra_obj)
        obj_ac1 = AltChildModel.objects.create(
            name="ac1", other_name="ac1name", link_on_altchild=plain_a_obj_1
        )
        obj_ac2 = AltChildModel.objects.create(
            name="ac2", other_name="ac2name", link_on_altchild=plain_a_obj_2
        )
        obj_p_1 = PlainModel.objects.create(relation=obj_p)
        obj_p_2 = PlainModel.objects.create(relation=obj_c)
        obj_p_3 = PlainModel.objects.create(relation=obj_ac1)
        obj_p_4 = PlainModel.objects.create(relation=obj_ac2)

        with self.assertNumQueries(1):
            # pos 3 if i cannot do optimized select_related
            obj_list = list(
                PlainModel.objects.select_related(
                    "relation",
                    "relation__childmodel__link_on_child",
                    "relation__altchildmodel__link_on_altchild",
                ).order_by("pk")
            )
        with self.assertNumQueries(0):
            self.assertEqual(obj_list[0].relation.name, "p1")
            self.assertEqual(obj_list[1].relation.name, "c1")
            self.assertEqual(obj_list[2].relation.name, "ac1")
            self.assertEqual(obj_list[3].relation.name, "ac2")
            obj_list[1].relation.link_on_child
            obj_list[2].relation.link_on_altchild
            obj_list[3].relation.link_on_altchild

    def test_select_related_on_poly_classes_supports_multi_level_inheritance(self):
        plain_a_obj_1 = PlainA.objects.create(field1="f1")
        plain_a_obj_2 = PlainA.objects.create(field1="f2")
        extra_obj = ModelExtraExternal.objects.create(topic="t1")
        obj_p = ParentModel.objects.create(name="p1")
        obj_c = ChildModel.objects.create(name="c1", other_name="c1name", link_on_child=extra_obj)
        obj_ac1 = AltChildModel.objects.create(
            name="ac1", other_name="ac1name", link_on_altchild=plain_a_obj_1
        )
        obj_acab2 = AltChildAsBaseModel.objects.create(
            name="ac2ab",
            other_name="acab2name",
            more_name="acab2morename",
            link_on_altchild=plain_a_obj_2,
        )

        obj_p_1 = PlainModel.objects.create(relation=obj_p)
        obj_p_2 = PlainModel.objects.create(relation=obj_c)
        obj_p_3 = PlainModel.objects.create(relation=obj_ac1)
        obj_p_4 = PlainModel.objects.create(relation=obj_acab2)

        with self.assertNumQueries(1):
            # pos 3 if i cannot do optimized select_related
            obj_list = list(
                PlainModel.objects.select_related(
                    "relation",
                    "relation__childmodel__link_on_child",
                    "relation__altchildmodel__link_on_altchild",
                    "relation__altchildmodel__altchildasbasemodel__link_on_altchild",
                ).order_by("pk")
            )
        with self.assertNumQueries(0):
            self.assertEqual(obj_list[0].relation.name, "p1")
            self.assertEqual(obj_list[1].relation.name, "c1")
            self.assertEqual(obj_list[2].relation.name, "ac1")
            self.assertEqual(obj_list[3].relation.name, "ac2ab")
            self.assertEqual(obj_list[3].relation.more_name, "acab2morename")
            obj_list[1].relation.link_on_child
            obj_list[2].relation.link_on_altchild
            obj_list[3].relation.link_on_altchild

    def test_select_related_on_poly_classes_with_modelname(self):
        plain_a_obj_1 = PlainA.objects.create(field1="f1")
        extra_obj = ModelExtraExternal.objects.create(topic="t1")
        obj_p = ParentModel.objects.create(name="p1")
        obj_c = ChildModel.objects.create(name="c1", other_name="c1name", link_on_child=extra_obj)
        obj_acab2 = AltChildAsBaseModel.objects.create(
            name="acab2",
            other_name="acab2name",
            more_name="acab2morename",
            link_on_altchild=plain_a_obj_1,
        )
        obj_p_1 = PlainModel.objects.create(relation=obj_p)
        obj_p_2 = PlainModel.objects.create(relation=obj_c)
        obj_p_3 = PlainModel.objects.create(relation=obj_acab2)

        ct = ContentType.objects.get_for_model(AltChildModel, for_concrete_model=True)

        with self.assertNumQueries(1):
            obj_list = list(
                PlainModel.objects.select_related(
                    "relation",
                    "relation__ChildModel__link_on_child",
                    "relation__AltChildAsBaseModel__link_on_altchild",
                ).order_by("pk")
            )

        with self.assertNumQueries(0):
            self.assertEqual(obj_list[0].relation.name, "p1")
            self.assertEqual(obj_list[1].relation.name, "c1")
            self.assertEqual(obj_list[2].relation.name, "acab2")
            obj_list[1].relation.link_on_child
            obj_list[2].relation.link_on_altchild

    def test_prefetch_related_from_basepoly(self):
        obja1 = NonSymRelationA.objects.create(field_a="fa1", field_base="fa1")
        obja2 = NonSymRelationA.objects.create(field_a="fa2", field_base="fa2")
        objb1 = NonSymRelationB.objects.create(field_b="fb1", field_base="fb1")
        objbc1 = NonSymRelationBC.objects.create(field_c="fbc1", field_base="fbc1")

        obja3 = NonSymRelationA.objects.create(field_a="fa3", field_base="fa3")
        # NOTE: these are symmetric links
        obja3.m2m.add(obja2)
        obja3.m2m.add(objb1)
        obja2.m2m.add(objbc1)

        # NOTE: prefetch content types so query asserts test data fetched.
        ct = ContentType.objects.get_for_model(NonSymRelationBase, for_concrete_model=True)

        with self.assertNumQueries(10):
            # query for  NonSymRelationBase (base)
            # query for  NonSymRelationA # level 1 (base)
            # query for  NonSymRelationB # level 1 (base)
            # query for  NonSymRelationBC # level 1 (base)
            # query for prefetch links (m2m)
            # query for  NonSymRelationA # level 2 (m2m)
            # query for  NonSymRelationB # level 2 (m2m)
            # query for  NonSymRelationBC # level 2 (m2m)
            # query for prefetch links (m2m__m2m)
            # query for  NonSymRelationA # level 3 (m2m__m2m)
            # query for  NonSymRelationB # level 3 (m2m__m2m) [SKIPPED AS NO DATA]
            # query for  NonSymRelationC # level 3 (m2m__m2m) [SKIPPED AS NO DATA]

            all_objs = {
                obj.pk: obj
                for obj in NonSymRelationBase.objects.prefetch_related("m2m", "m2m__m2m")
            }

        with self.assertNumQueries(0):
            relations = {obj.pk: set(obj.m2m.all()) for obj in all_objs.values()}

        with self.assertNumQueries(0):
            sub_relations = {a.pk: set(a.m2m.all()) for a in all_objs.get(obja3.pk).m2m.all()}

        self.assertDictEqual(
            {
                obja1.pk: set(),
                obja2.pk: set([objbc1]),
                obja3.pk: set([obja2, objb1]),
                objb1.pk: set([]),
                objbc1.pk: set([]),
            },
            relations,
        )

        self.assertDictEqual(
            {
                obja2.pk: set([objbc1]),
                objb1.pk: set([]),
            },
            sub_relations,
        )

    def test_prefetch_related_from_subclass(self):
        obja1 = NonSymRelationA.objects.create(field_a="fa1", field_base="fa1")
        obja2 = NonSymRelationA.objects.create(field_a="fa2", field_base="fa2")
        objb1 = NonSymRelationB.objects.create(field_b="fb1", field_base="fb1")
        objbc1 = NonSymRelationBC.objects.create(field_c="fbc1", field_base="fbc1")

        obja3 = NonSymRelationA.objects.create(field_a="fa3", field_base="fa3")
        # NOTE: these are symmetric links
        obja3.m2m.add(obja2)
        obja3.m2m.add(objb1)
        obja2.m2m.add(objbc1)

        # NOTE: prefetch content types so query asserts test data fetched.
        ct = ContentType.objects.get_for_model(NonSymRelationBase, for_concrete_model=True)

        with self.assertNumQueries(7):
            # query for  NonSymRelationA # level 1 (base)
            # query for prefetch links (m2m)
            # query for  NonSymRelationA # level 2 (m2m)
            # query for  NonSymRelationB # level 2 (m2m)
            # query for  NonSymRelationBC # level 2 (m2m)
            # query for prefetch links (m2m__m2m)
            # query for  NonSymRelationA # level 3 (m2m__m2m)
            # query for  NonSymRelationB # level 3 (m2m__m2m) [SKIPPED AS NO DATA]
            # query for  NonSymRelationC # level 3 (m2m__m2m) [SKIPPED AS NO DATA]

            all_objs = {
                obj.pk: obj for obj in NonSymRelationA.objects.prefetch_related("m2m", "m2m__m2m")
            }

        with self.assertNumQueries(0):
            relations = {obj.pk: set(obj.m2m.all()) for obj in all_objs.values()}

        with self.assertNumQueries(0):
            sub_relations = {a.pk: set(a.m2m.all()) for a in all_objs.get(obja3.pk).m2m.all()}

        self.assertDictEqual(
            {
                obja1.pk: set(),
                obja2.pk: set([objbc1]),
                obja3.pk: set([obja2, objb1]),
            },
            relations,
        )

        self.assertDictEqual(
            {
                obja2.pk: set([objbc1]),
                objb1.pk: set([]),
            },
            sub_relations,
        )

    def test_select_related_field_from_polymorphic_child_class(self):
        # 198
        obj_p1 = ParentModel.objects.create(name="p1")
        obj_p2 = ParentModel.objects.create(name="p2")
        obj_p3 = ParentModel.objects.create(name="p4")
        obj_c1 = ChildModel.objects.create(name="c1", other_name="c1name")
        obj_c2 = ChildModel.objects.create(name="c2", other_name="c2name")
        obj_ac1 = AltChildModel.objects.create(name="ac1", other_name="ac1name")
        obj_ac2 = AltChildModel.objects.create(name="ac2", other_name="ac2name")
        obj_ac3 = AltChildModel.objects.create(name="ac3", other_name="ac3name")

        with self.assertNumQueries(2):
            # Queries will be
            #    * 1 for All ParentModel object (x4 +bases of all)
            #    * 1 for ChildModel object (x2)
            #    * 0 for AltChildModel object as from select_related (x3)
            all_objs = [
                obj
                for obj in ParentModel.objects.select_related(
                    "altchildmodel",
                )
            ]

    def test_select_related_field_from_polymorphic_child_class_using_modelnames_level1(self):
        # 198
        obj_p1 = ParentModel.objects.create(name="p1")
        obj_p2 = ParentModel.objects.create(name="p2")
        obj_p3 = ParentModel.objects.create(name="p4")
        obj_c1 = ChildModel.objects.create(name="c1", other_name="c1name")
        obj_c2 = ChildModel.objects.create(name="c2", other_name="c2name")
        obj_ac1 = AltChildModel.objects.create(name="ac1", other_name="ac1name")
        obj_ac2 = AltChildModel.objects.create(name="ac2", other_name="ac2name")
        obj_ac3 = AltChildModel.objects.create(name="ac3", other_name="ac3name")

        with self.assertNumQueries(2):
            # Queries will be
            #    * 1 for All ParentModel object (x4 +bases of all)
            #    * 1 for ChildModel object (x2)
            #    * 0 for AltChildModel object as from select_related (x3)
            all_objs = [
                obj
                for obj in ParentModel.objects.select_related(
                    "AltChildModel",
                )
            ]

    def test_select_related_field_from_polymorphic_child_class_using_modelnames_multi_level(self):
        plain_a_obj_1 = PlainA.objects.create(field1="f1")

        obj_p1 = ParentModel.objects.create(name="p1")
        obj_acab2 = AltChildAsBaseModel.objects.create(
            name="acab2",
            other_name="acab2name",
            more_name="acab2morename",
            link_on_altchild=plain_a_obj_1,
        )
        obj_c1 = ChildModel.objects.create(name="c1", other_name="c1name")
        obj_ac3 = ChildModel.objects.create(name="c2", other_name="c3name")

        # NOTE: prefetch content types so query asserts test data fetched.
        ct = ContentType.objects.get_for_model(AltChildModel, for_concrete_model=True)

        with self.assertNumQueries(2):
            # Queries will be
            #    * 1 for All ParentModel object (x4 +bases of all)
            #    * 1 for ChildModel object (x1)
            #    * 0 for AltChildAsBaseModel object as from select_related (x1)
            #    * 0 for AltChildModel object as part of select_related form
            #        AltChildAsBaseModel (x1)
            [obj for obj in ParentModel.objects.select_related("AltChildAsBaseModel")]

    def test_prefetch_object_is_supported(self):
        b1 = RelatingModel.objects.create()
        b2 = RelatingModel.objects.create()

        rel1 = Model2A.objects.create(field1="A1")
        rel2 = Model2B.objects.create(field1="A2", field2="B2")

        b1.many2many.add(rel1)
        b2.many2many.add(rel2)

        rel2.delete(keep_parents=True)

        qs = RelatingModel.objects.order_by("pk").prefetch_related(
            Prefetch("many2many", queryset=Model2A.objects.all(), to_attr="poly"),
            Prefetch("many2many", queryset=Model2A.objects.non_polymorphic(), to_attr="non_poly"),
        )

        objects = list(qs)
        self.assertEqual(len(objects[0].poly), 1)

        # derived object was not fetched
        self.assertEqual(len(objects[1].poly), 0)

        # base object always found
        self.assertEqual(len(objects[0].non_poly), 1)
        self.assertEqual(len(objects[1].non_poly), 1)

    def test_select_related_on_poly_classes_preserves_on_relations_annotations(self):
        b1 = RelatingModel.objects.create()
        b2 = RelatingModel.objects.create()
        b3 = RelatingModel.objects.create()

        rel1 = Model2A.objects.create(field1="A1")
        rel2 = Model2B.objects.create(field1="A2", field2="B2")

        b1.many2many.add(rel1)
        b2.many2many.add(rel2)
        b3.many2many.add(rel2)

        qs = RelatingModel.objects.order_by("pk").prefetch_related(
            Prefetch(
                "many2many",
                queryset=Model2A.objects.annotate(Count("relatingmodel")),
                to_attr="poly",
            )
        )

        objects = list(qs)
        self.assertEqual(objects[0].poly[0].relatingmodel__count, 1)
        self.assertEqual(objects[1].poly[0].relatingmodel__count, 2)
        self.assertEqual(objects[2].poly[0].relatingmodel__count, 2)

    @expectedFailure
    def test_prefetch_loading_relation_only_on_some_poly_model(self):
        plain_a_obj_1 = PlainA.objects.create(field1="p1")
        plain_a_obj_2 = PlainA.objects.create(field1="p2")
        plain_a_obj_3 = PlainA.objects.create(field1="p3")
        plain_a_obj_4 = PlainA.objects.create(field1="p4")
        plain_a_obj_5 = PlainA.objects.create(field1="p5")

        ac_m2m_obj = AltChildWithM2MModel.objects.create(
            other_name="o1",
        )
        ac_m2m_obj.m2m.set([plain_a_obj_1, plain_a_obj_2, plain_a_obj_3])

        cm_1 = ChildModel.objects.create(other_name="c1")
        cm_2 = ChildModel.objects.create(other_name="c2")
        cm_3 = ChildModel.objects.create(other_name="c3")

        acm_1 = AltChildModel.objects.create(other_name="ac3", link_on_altchild=plain_a_obj_4)
        acm_2 = AltChildModel.objects.create(other_name="ac3", link_on_altchild=plain_a_obj_5)

        pm_1 = PlainModelWithM2M.objects.create(field1="pm1")
        pm_2 = PlainModelWithM2M.objects.create(field1="pm2")

        pm_1.m2m.set([cm_1, cm_2])
        pm_2.m2m.set(
            [
                cm_3,
            ]
        )

        # NOTE: prefetch content types so query asserts test data fetched.
        ct = ContentType.objects.get_for_model(ParentModel, for_concrete_model=True)

        pm_2.m2m.set([ac_m2m_obj])
        with self.assertNumQueries(4):
            # query for PlainModelWithM2M # level 1 (base)
            # query for prefetch links (m2m)
            # query for ChildModel # level 2 (m2m)
            # query for AltChildWithM2MModel # level 2 (m2m)
            qs = PlainModelWithM2M.objects.all()
            qs = qs.prefetch_related("m2m__altchildmodel__altchildWithm2mmodel__m2m")
            list(qs)

    @expectedFailure
    def test_prefetch_loading_relation_only_on_some_poly_model_using_modelnames(self):
        plain_a_obj_1 = PlainA.objects.create(field1="p1")
        plain_a_obj_2 = PlainA.objects.create(field1="p2")
        plain_a_obj_3 = PlainA.objects.create(field1="p3")
        plain_a_obj_4 = PlainA.objects.create(field1="p4")
        plain_a_obj_5 = PlainA.objects.create(field1="p5")

        ac_m2m_obj = AltChildWithM2MModel.objects.create(
            other_name="o1",
        )
        ac_m2m_obj.m2m.set([plain_a_obj_1, plain_a_obj_2, plain_a_obj_3])

        cm_1 = ChildModel.objects.create(other_name="c1")
        cm_2 = ChildModel.objects.create(other_name="c2")
        cm_3 = ChildModel.objects.create(other_name="c3")

        acm_1 = AltChildModel.objects.create(other_name="ac3", link_on_altchild=plain_a_obj_4)
        acm_2 = AltChildModel.objects.create(other_name="ac3", link_on_altchild=plain_a_obj_5)

        pm_1 = PlainModelWithM2M.objects.create(field1="pm1")
        pm_2 = PlainModelWithM2M.objects.create(field1="pm2")

        pm_1.m2m.set([cm_1, cm_2])
        pm_2.m2m.set(
            [
                cm_3,
            ]
        )

        # NOTE: prefetch content types so query asserts test data fetched.
        ct = ContentType.objects.get_for_model(ParentModel, for_concrete_model=True)

        pm_2.m2m.set([ac_m2m_obj])
        with self.assertNumQueries(4):
            # query for PlainModelWithM2M # level 1 (base)
            # query for prefetch links (m2m)
            # query for ChildModel # level 2 (m2m)
            # query for AltChildWithM2MModel # level 2 (m2m)
            qs = PlainModelWithM2M.objects.all()
            qs = qs.prefetch_related("m2m__AltChildWithM2MModel__m2m")
            list(qs)
